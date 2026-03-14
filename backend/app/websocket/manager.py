from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import json
import asyncio

from app.database import async_session
from app.services.room_service import RoomService
from app.services.user_service import UserService
from app.game.engine import GameEngine, GamePhase, ActionType
from app.models.room import RoomStatus, SeatStatus

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for rooms."""

    def __init__(self):
        # room_id -> set of websocket connections
        self.room_connections: Dict[int, Set[WebSocket]] = {}
        # websocket -> user_id
        self.connection_user: Dict[WebSocket, int] = {}
        # room_id -> game engine
        self.room_games: Dict[int, GameEngine] = {}
        # user_id -> room_id (for reconnect)
        self.user_room: Dict[int, int] = {}
        # user_id -> disconnect time
        self.disconnect_times: Dict[int, float] = {}
        # user_id -> True (player wants to stop after current hand)
        self.stop_requested: Dict[int, bool] = {}
        # room_id -> True (owner stopped game, end after current hand)
        self.game_stop_requested: Dict[int, bool] = {}

    async def connect(self, websocket: WebSocket, room_id: int, user_id: int):
        await websocket.accept()
        if room_id not in self.room_connections:
            self.room_connections[room_id] = set()
        self.room_connections[room_id].add(websocket)
        self.connection_user[websocket] = user_id
        self.user_room[user_id] = room_id

        # Clear disconnect time if reconnecting
        if user_id in self.disconnect_times:
            del self.disconnect_times[user_id]

    def disconnect(self, websocket: WebSocket, room_id: int):
        if room_id in self.room_connections:
            self.room_connections[room_id].discard(websocket)
        if websocket in self.connection_user:
            user_id = self.connection_user[websocket]
            del self.connection_user[websocket]
            # Record disconnect time for potential reconnect
            import time
            self.disconnect_times[user_id] = time.time()

    async def broadcast_to_room(self, room_id: int, message: dict):
        if room_id in self.room_connections:
            for connection in self.room_connections[room_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

    async def send_to_user(self, user_id: int, message: dict):
        for ws, uid in self.connection_user.items():
            if uid == user_id:
                try:
                    await ws.send_json(message)
                except:
                    pass

    def get_game(self, room_id: int) -> Optional[GameEngine]:
        return self.room_games.get(room_id)

    def set_game(self, room_id: int, game: GameEngine):
        self.room_games[room_id] = game

    def remove_game(self, room_id: int):
        if room_id in self.room_games:
            del self.room_games[room_id]


manager = ConnectionManager()


async def get_user_from_token(token: str, db: AsyncSession) -> Optional[int]:
    """Validate JWT token and return user_id."""
    from jose import jwt, JWTError
    from app.config import settings

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        return int(user_id_str)
    except (JWTError, ValueError):
        return None


@router.websocket("/ws/room/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, token: str):
    async with async_session() as db:
        # Validate token
        user_id = await get_user_from_token(token, db)
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return

        # Get user info
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)
        if not user:
            await websocket.close(code=4002, reason="User not found")
            return

        # Get room info
        room_service = RoomService(db)
        room = await room_service.get_room_by_id(room_id)
        if not room:
            await websocket.close(code=4003, reason="Room not found")
            return

        # Connect
        await manager.connect(websocket, room_id, user_id)

        try:
            # Send current game state
            game = manager.get_game(room_id)
            if game:
                await websocket.send_json({
                    "type": "game_state",
                    "data": game.get_state(user_id)
                })

            # Broadcast user joined
            await broadcast_room_state(room_id, db)
            await manager.broadcast_to_room(room_id, {
                "type": "user_joined",
                "data": {
                    "user_id": user_id,
                    "username": user.display_name
                }
            })

            # Handle messages
            while True:
                data = await websocket.receive_json()
                await handle_message(websocket, room_id, user_id, data, db)

        except WebSocketDisconnect:
            manager.disconnect(websocket, room_id)
            await manager.broadcast_to_room(room_id, {
                "type": "user_left",
                "data": {
                    "user_id": user_id,
                    "username": user.display_name
                }
            })
        except Exception as e:
            manager.disconnect(websocket, room_id)


async def handle_message(
    websocket: WebSocket,
    room_id: int,
    user_id: int,
    data: dict,
    db: AsyncSession
):
    """Handle WebSocket messages."""
    msg_type = data.get("type")
    msg_data = data.get("data", {})

    print(f"[WS] Received message: type={msg_type}, user_id={user_id}, room_id={room_id}")

    room_service = RoomService(db)
    user_service = UserService(db)
    room = await room_service.get_room_by_id(room_id)

    if not room:
        return

    if msg_type == "chat":
        # Chat message
        user = await user_service.get_user_by_id(user_id)
        await manager.broadcast_to_room(room_id, {
            "type": "chat",
            "data": {
                "user_id": user_id,
                "username": user.display_name,
                "message": msg_data.get("message", "")[:500]
            }
        })

    elif msg_type == "ready":
        # Player ready
        seat = await room_service.update_seat_status(room, user_id, SeatStatus.READY)
        if seat:
            await broadcast_room_state(room_id, db)

    elif msg_type == "unready":
        # Player unready
        game = manager.get_game(room_id)
        if game and game.phase not in [GamePhase.ENDED]:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "游戏中无法取消准备"}
            })
            return
        seat = await room_service.update_seat_status(room, user_id, SeatStatus.WAITING)
        if seat:
            await broadcast_room_state(room_id, db)

    elif msg_type == "start_game":
        # Start game (owner only)
        print(f"[WS] Start game request from user {user_id}, owner is {room.owner_id}")
        if room.owner_id != user_id:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "只有房主可以开始游戏"}
            })
            return

        game = manager.get_game(room_id)
        if game and game.phase not in [GamePhase.ENDED]:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "游戏已在进行中"}
            })
            return

        # Check if can start
        can_start, msg = await room_service.can_start_game(room)
        print(f"[WS] Can start: {can_start}, message: {msg}")
        if not can_start:
            await websocket.send_json({
                "type": "error",
                "data": {"message": msg}
            })
            return

        # Create game engine
        game = GameEngine(
            small_blind=room.small_blind,
            big_blind=room.big_blind
        )

        # Add players
        ready_seats = await room_service.get_ready_players(room_id)
        for seat in ready_seats:
            user = await user_service.get_user_by_id(seat.user_id)
            game.add_player(seat.user_id, user.display_name, seat.seat_index, seat.chips)

        # Set callback for game complete
        async def on_hand_complete(result):
            await handle_hand_complete(room_id, result, db)

        game.on_hand_complete = on_hand_complete

        manager.set_game(room_id, game)

        # Update room status
        await room_service.update_room_status(room, RoomStatus.PLAYING)

        # Update seat status
        for seat in ready_seats:
            await room_service.update_seat_status(room, seat.user_id, SeatStatus.PLAYING)

        # Start hand
        success = game.start_hand()
        if not success:
            print(f"[WS] Failed to start hand")
            # Rollback seat status
            for seat in ready_seats:
                await room_service.update_seat_status(room, seat.user_id, SeatStatus.READY)
            manager.remove_game(room_id)
            await room_service.update_room_status(room, RoomStatus.WAITING)
            await websocket.send_json({
                "type": "error",
                "data": {"message": "无法开始游戏"}
            })
            return

        # Broadcast game state
        await broadcast_game_state(room_id)

    elif msg_type == "action":
        # Game action
        game = manager.get_game(room_id)
        if not game:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "游戏未开始"}
            })
            return

        action_str = msg_data.get("action")
        amount = msg_data.get("amount", 0)

        print(f"[WS] Action received: user_id={user_id}, action={action_str}, amount={amount}")
        print(f"[WS] Current player: {game.get_current_player().user_id if game.get_current_player() else None}")
        print(f"[WS] Player is_current: {game.players.get(user_id).is_current if game.players.get(user_id) else 'N/A'}")

        try:
            action = ActionType(action_str)
        except ValueError:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "无效操作"}
            })
            return

        success, msg = game.execute_action(user_id, action, amount)
        print(f"[WS] Action result: success={success}, message={msg}")

        if not success:
            await websocket.send_json({
                "type": "error",
                "data": {"message": msg}
            })
            return

        # Broadcast updated state
        await broadcast_game_state(room_id)

        # Check if hand ended
        if game.phase == GamePhase.ENDED:
            await handle_hand_end(room_id, db)

    elif msg_type == "next_hand":
        # Start next hand
        game = manager.get_game(room_id)
        if not game:
            return

        # Check if players want to continue
        can_start, msg = game.can_start()
        if not can_start:
            await manager.broadcast_to_room(room_id, {
                "type": "game_ended",
                "data": {"message": msg}
            })
            manager.remove_game(room_id)
            await room_service.update_room_status(room, RoomStatus.WAITING)
            return

        # Reset player statuses
        for player in game.players.values():
            seat = await room_service.update_seat_status(room, player.user_id, SeatStatus.PLAYING)
            if seat:
                seat.chips = player.chips
                await db.commit()

        game.start_hand()
        await broadcast_game_state(room_id)

    elif msg_type == "stop_game":
        # Player wants to stop after current hand
        manager.stop_requested[user_id] = True

        # If owner stops, mark game to end after this hand
        if room.owner_id == user_id:
            manager.game_stop_requested[room_id] = True
            await manager.broadcast_to_room(room_id, {
                "type": "info",
                "data": {"message": "房主已请求停止游戏，本局结束后将停止"}
            })
        else:
            await websocket.send_json({
                "type": "info",
                "data": {"message": "已请求停止游戏，本局结束后将取消准备"}
            })


async def broadcast_room_state(room_id: int, db: AsyncSession):
    """Broadcast room state to all connections."""
    room_service = RoomService(db)
    room = await room_service.get_room_by_id(room_id)
    if room:
        seats = await room_service.get_room_seats(room_id)
        user_service = UserService(db)

        seat_data = []
        for seat in seats:
            user_name = None
            if seat.user_id:
                user = await user_service.get_user_by_id(seat.user_id)
                user_name = user.display_name if user else None
            seat_data.append({
                "seat_index": seat.seat_index,
                "user_id": seat.user_id,
                "user_name": user_name,
                "chips": seat.chips,
                "net_chips": seat.net_chips,
                "status": seat.status.value if hasattr(seat.status, 'value') else seat.status
            })

        await manager.broadcast_to_room(room_id, {
            "type": "room_state",
            "data": {
                "room_id": room_id,
                "status": room.status.value if hasattr(room.status, 'value') else room.status,
                "seats": seat_data
            }
        })


async def broadcast_game_state(room_id: int):
    """Broadcast game state to all connections."""
    game = manager.get_game(room_id)
    if game:
        # Send personalized state to each user
        for ws in manager.room_connections.get(room_id, []):
            user_id = manager.connection_user.get(ws)
            if user_id:
                try:
                    state = game.get_state(user_id)
                    state["room_id"] = room_id
                    await ws.send_json({
                        "type": "game_state",
                        "data": state
                    })
                except:
                    pass


async def handle_hand_complete(room_id: int, result, db: AsyncSession):
    """Handle hand completion callback."""
    # Build detailed result message
    result_lines = []

    # Get player names from result
    player_names = result.player_names or {}
    chip_changes = result.chip_changes or {}

    # Add winner information
    for winner in result.winners:
        winner_name = player_names.get(winner["user_id"], f"玩家{winner['user_id']}")
        hand_info = f" ({winner['hand']})" if winner.get("hand") else ""
        result_lines.append(f"🏆 {winner_name} 赢得 {winner['amount']} 筹码{hand_info}")

    # Add showdown hands if available (only for players who showed cards)
    if result.player_hands and len(result.player_hands) > 0:
        result_lines.append("--- 开牌信息 ---")
        for uid, cards in result.player_hands.items():
            player_name = player_names.get(uid, f"玩家{uid}")
            cards_str = " ".join([f"{c.rank}{get_suit_symbol(c.suit)}" for c in cards])
            result_lines.append(f"{player_name}: {cards_str}")

    # Add chip changes for all players who participated
    if chip_changes:
        result_lines.append("--- 筹码变动 ---")
        for uid, change in chip_changes.items():
            if change != 0:  # Only show players with chip changes
                player_name = player_names.get(uid, f"玩家{uid}")
                if change > 0:
                    result_lines.append(f"{player_name}: +{change}")
                else:
                    result_lines.append(f"{player_name}: {change}")

    await manager.broadcast_to_room(room_id, {
        "type": "hand_complete",
        "data": {
            "winners": result.winners,
            "pot_amount": result.pot_amount,
            "community_cards": [
                {"rank": c.rank, "suit": c.suit}
                for c in result.community_cards
            ],
            "player_hands": {
                str(uid): [
                    {"rank": c.rank, "suit": c.suit}
                    for c in cards
                ]
                for uid, cards in result.player_hands.items()
            },
            "player_names": player_names,
            "chip_changes": chip_changes,
            "result_message": "\n".join(result_lines)
        }
    })


def get_suit_symbol(suit: str) -> str:
    """Convert suit code to symbol."""
    symbols = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}
    return symbols.get(suit, suit)


async def handle_hand_end(room_id: int, db: AsyncSession):
    """Handle end of a hand."""
    game = manager.get_game(room_id)
    room_service = RoomService(db)
    room = await room_service.get_room_by_id(room_id)

    if not game or not room:
        return

    # Update seat chips
    for player in game.players.values():
        from sqlalchemy import select, and_
        from app.models.room import Seat

        result = await db.execute(
            select(Seat).where(
                and_(Seat.room_id == room_id, Seat.user_id == player.user_id)
            )
        )
        seat = result.scalar_one_or_none()
        if seat:
            seat.chips = player.chips
            seat.net_chips = player.total_bet - player.chips  # Simplified net calculation

    await db.commit()

    # Broadcast updated state
    await broadcast_game_state(room_id)

    # Handle players who requested to stop
    players_to_unready = []
    for player in game.players.values():
        if manager.stop_requested.pop(player.user_id, False):
            players_to_unready.append(player.user_id)

    # Check if owner requested to stop the game
    should_stop = manager.game_stop_requested.pop(room_id, False)

    if should_stop:
        # Owner stopped the game
        await manager.broadcast_to_room(room_id, {
            "type": "game_ended",
            "data": {"message": "房主已停止游戏"}
        })
        manager.remove_game(room_id)
        await room_service.update_room_status(room, RoomStatus.WAITING)
        # Set all players to waiting
        for player in game.players.values():
            await room_service.update_seat_status(room, player.user_id, SeatStatus.WAITING)
        await broadcast_room_state(room_id, db)
    else:
        # Set players who requested to stop to waiting status
        for user_id in players_to_unready:
            await room_service.update_seat_status(room, user_id, SeatStatus.WAITING)

        # Check if we can start another hand
        can_start, msg = game.can_start()
        if can_start:
            # Small delay before starting next hand
            await asyncio.sleep(3)

            # Update room status
            await room_service.update_room_status(room, RoomStatus.PLAYING)

            # Reset player statuses for new hand
            for player in game.players.values():
                if player.user_id not in players_to_unready:
                    await room_service.update_seat_status(room, player.user_id, SeatStatus.PLAYING)

            await db.commit()
            game.start_hand()
            await broadcast_game_state(room_id)
        else:
            # Not enough players, end game
            await manager.broadcast_to_room(room_id, {
                "type": "game_ended",
                "data": {"message": msg}
            })
            manager.remove_game(room_id)
            await room_service.update_room_status(room, RoomStatus.WAITING)
            for player in game.players.values():
                await room_service.update_seat_status(room, player.user_id, SeatStatus.WAITING)
            await broadcast_room_state(room_id, db)
