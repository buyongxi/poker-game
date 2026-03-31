import logging
import time
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional
from jose import jwt, JWTError

from app.services.room_service import RoomService
from app.services.user_service import UserService
from app.game.engine import GameEngine, GamePhase, ActionType
from app.game.player import PlayerStatus
from app.models.room import RoomStatus, SeatStatus
from app.database import async_session
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


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
        # room_id -> asyncio.Task for action timeout
        self.timeout_tasks: Dict[int, asyncio.Task] = {}
        # room_id -> time when current action started
        self.action_start_times: Dict[int, float] = {}
        # room_id -> last known phase (for detecting dealing)
        self.last_known_phase: Dict[int, str] = {}
        # Cleanup task for disconnect timeouts
        self.cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """Start background task to clean up timed-out disconnections."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(60)  # Check every minute
                    await self._cleanup_disconnected_players()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in disconnect cleanup task: {e}")

        self.cleanup_task = asyncio.create_task(cleanup_loop())

    async def _cleanup_disconnected_players(self):
        """Remove players who have been disconnected for too long."""
        current_time = time.time()
        timeout = settings.RECONNECT_TIMEOUT

        users_to_remove = []
        for user_id, disconnect_time in list(self.disconnect_times.items()):
            if current_time - disconnect_time > timeout:
                users_to_remove.append(user_id)

        for user_id in users_to_remove:
            room_id = self.user_room.get(user_id)
            if room_id:
                logger.info(f"Removing user {user_id} from room {room_id} due to disconnect timeout")
                room_service = RoomService()
                await room_service.leave_room(room_id, user_id)
                await broadcast_room_state(room_id)

            # Clean up tracking
            if user_id in self.disconnect_times:
                del self.disconnect_times[user_id]
            if user_id in self.user_room:
                del self.user_room[user_id]

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
            self.disconnect_times[user_id] = time.time()

    def cancel_timeout(self, room_id: int):
        """Cancel any pending timeout task for a room."""
        if room_id in self.timeout_tasks:
            self.timeout_tasks[room_id].cancel()
            del self.timeout_tasks[room_id]

    def start_delayed_timeout(self, room_id: int, user_id: int, game: GameEngine):
        """Start a timeout task for the current player after a dealing delay."""
        self.cancel_timeout(room_id)

        # Record action start time (will be set after delay)
        self.action_start_times[room_id] = time.time() + game.dealing_delay

        async def delayed_timeout_task():
            # Wait for dealing delay
            await asyncio.sleep(game.dealing_delay)
            # Now set the actual action start time
            self.action_start_times[room_id] = time.time()
            # Then wait for action timeout
            await asyncio.sleep(game.action_timeout)
            # Timeout occurred - auto fold
            await handle_timeout_fold(room_id, user_id)

        self.timeout_tasks[room_id] = asyncio.create_task(delayed_timeout_task())

    def get_remaining_time(self, room_id: int, game: GameEngine) -> Optional[int]:
        """Get remaining time for current action in seconds."""
        if room_id not in self.action_start_times:
            return None
        elapsed = time.time() - self.action_start_times[room_id]
        remaining = max(0, int(game.action_timeout - elapsed))
        return remaining

    async def broadcast_to_room(self, room_id: int, message: dict):
        logger.debug(f"broadcast_to_room: room_id={room_id}, message_type={message.get('type')}")
        if room_id in self.room_connections:
            connections = self.room_connections[room_id]
            logger.debug(f"broadcast_to_room: {len(connections)} connections in room")
            for connection in connections:
                try:
                    await connection.send_json(message)
                    logger.debug(f"broadcast_to_room: sent to connection")
                except Exception as e:
                    logger.error(f"broadcast_to_room: failed to send: {e}")
        else:
            logger.debug(f"broadcast_to_room: no connections for room {room_id}")

    async def send_to_user(self, user_id: int, message: dict):
        for ws, uid in self.connection_user.items():
            if uid == user_id:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"send_to_user: failed to send to user {user_id}: {e}")

    def get_game(self, room_id: int) -> Optional[GameEngine]:
        return self.room_games.get(room_id)

    def set_game(self, room_id: int, game: GameEngine):
        self.room_games[room_id] = game

    def remove_game(self, room_id: int):
        if room_id in self.room_games:
            del self.room_games[room_id]

    def get_seat_by_user(self, room: 'MemoryRoom', user_id: int) -> Optional['MemorySeat']:
        """Get a seat by user_id from memory room."""
        for seat in room.seats.values():
            if seat.user_id == user_id:
                return seat
        return None

    def get_ready_players(self, room: 'MemoryRoom') -> list:
        """Get list of ready players with chips > 0 from memory room."""
        ready = []
        for seat in room.seats.values():
            if seat.status == SeatStatus.READY and seat.chips > 0 and seat.user_id:
                ready.append(seat)
        return ready

    def get_room_seats_list(self, room: 'MemoryRoom') -> list:
        """Get list of all seats for broadcasting from memory room."""
        seats = []
        for seat_index in sorted(room.seats.keys()):
            seat = room.seats[seat_index]
            seats.append({
                "seat_index": seat.seat_index,
                "user_id": seat.user_id,
                "user_name": seat.user_name,
                "chips": seat.chips,
                "total_buyin": seat.total_buyin,
                "net_chips": seat.chips - seat.total_buyin,  # 净筹码 = 筹码 - 买入
                "status": seat.status.value if hasattr(seat.status, 'value') else seat.status
            })
        return seats

    def remove_room(self, room_id: int):
        """Remove room from memory and clean up all associated resources."""
        if room_id in self.room_connections:
            del self.room_connections[room_id]
        if room_id in self.room_games:
            del self.room_games[room_id]
        if room_id in self.timeout_tasks:
            self.timeout_tasks[room_id].cancel()
            del self.timeout_tasks[room_id]
        if room_id in self.action_start_times:
            del self.action_start_times[room_id]
        if room_id in self.last_known_phase:
            del self.last_known_phase[room_id]
        if room_id in self.game_stop_requested:
            del self.game_stop_requested[room_id]

        # Clean up disconnect times for users in this room
        users_to_remove = [uid for uid, rid in self.user_room.items() if rid == room_id]
        for user_id in users_to_remove:
            if user_id in self.disconnect_times:
                del self.disconnect_times[user_id]
            if user_id in self.user_room:
                del self.user_room[user_id]
            if user_id in self.stop_requested:
                del self.stop_requested[user_id]


manager = ConnectionManager()


async def get_user_from_token(token: str) -> Optional[int]:
    """Validate JWT token and return user_id."""
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
    # Validate token
    user_id = await get_user_from_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Get user info from database (users are still persisted)
    async with async_session() as db:
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)
        if not user:
            await websocket.close(code=4002, reason="User not found")
            return

        # Get room info from memory
        room_service = RoomService()
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
            await broadcast_room_state(room_id)
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
                await handle_message(websocket, room_id, user_id, data)

        except WebSocketDisconnect:
            manager.disconnect(websocket, room_id)
            # Don't leave the room - just record disconnect time
            # Player can reconnect within RECONNECT_TIMEOUT
            # Notify other players that this player disconnected
            await manager.broadcast_to_room(room_id, {
                "type": "user_disconnected",
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
    data: dict
):
    """Handle WebSocket messages."""
    msg_type = data.get("type")
    msg_data = data.get("data", {})

    logger.debug(f"Received message: type={msg_type}, user_id={user_id}, room_id={room_id}")

    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)

    if not room:
        return

    if msg_type == "chat":
        # Chat message - get user name from memory room
        seat = manager.get_seat_by_user(room, user_id)
        user_name = seat.user_name if seat else f"玩家{user_id}"
        await manager.broadcast_to_room(room_id, {
            "type": "chat",
            "data": {
                "user_id": user_id,
                "username": user_name,
                "message": msg_data.get("message", "")[:settings.MAX_CHAT_LENGTH]
            }
        })

    elif msg_type == "ready":
        # Player ready - check if they have chips first (use memory)
        mem_seat = manager.get_seat_by_user(room, user_id)
        if not mem_seat:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "你不在该房间中"}
            })
            return

        if mem_seat.chips <= 0:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "筹码不足，请先补充筹码"}
            })
            return

        # Update memory
        await room_service.update_seat_status(room, user_id, SeatStatus.READY)
        await broadcast_room_state(room_id)

    elif msg_type == "unready":
        # Player unready - during game this marks them to not participate in next hand
        game = manager.get_game(room_id)
        if game and game.phase not in [GamePhase.ENDED]:
            # During game, mark player to stop after current hand
            manager.stop_requested[user_id] = True

            # If owner unready, stop the game after current hand
            if room.owner_id == user_id:
                manager.game_stop_requested[room_id] = True
                await manager.broadcast_to_room(room_id, {
                    "type": "info",
                    "data": {"message": "房主已取消准备，本局结束后将停止游戏"}
                })
            else:
                await websocket.send_json({
                    "type": "info",
                    "data": {"message": "已取消准备，本局结束后将不会参与下一局"}
                })
        else:
            # Not in game, just set status to waiting
            await room_service.update_seat_status(room, user_id, SeatStatus.WAITING)
            await broadcast_room_state(room_id)

    elif msg_type == "start_game":
        # Start game (owner only)
        logger.debug(f"Start game request from user {user_id}, owner is {room.owner_id}")
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

        # Check if can start (use memory)
        ready_players = manager.get_ready_players(room)
        if len(ready_players) < 2:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "需要至少2名玩家准备"}
            })
            return

        # Create game engine
        game = GameEngine(
            small_blind=room.small_blind,
            big_blind=room.big_blind
        )

        # Add players from memory
        for mem_seat in ready_players:
            game.add_player(mem_seat.user_id, mem_seat.user_name, mem_seat.seat_index, mem_seat.chips)

        # Set callback for game complete
        async def on_hand_complete(result):
            await handle_hand_complete(room_id, result)

        game.on_hand_complete = on_hand_complete

        manager.set_game(room_id, game)

        # Update room status in memory
        await room_service.update_room_status(room, RoomStatus.PLAYING)

        # Update seat status
        for mem_seat in ready_players:
            await room_service.update_seat_status(room, mem_seat.user_id, SeatStatus.PLAYING)

        # Start hand
        success = game.start_hand()
        if not success:
            logger.debug(f"Failed to start hand")
            # Rollback seat status
            for mem_seat in ready_players:
                await room_service.update_seat_status(room, mem_seat.user_id, SeatStatus.READY)
            manager.remove_game(room_id)
            await room_service.update_room_status(room, RoomStatus.WAITING)
            await websocket.send_json({
                "type": "error",
                "data": {"message": "无法开始游戏"}
            })
            return

        # Broadcast game state
        await broadcast_game_state(room_id)

        # Check if hand ended immediately (e.g., both blinds all-in)
        if game.phase == GamePhase.ENDED:
            await handle_hand_end(room_id)

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

        logger.debug(f"Action received: user_id={user_id}, action={action_str}, amount={amount}")
        logger.debug(f"Current player: {game.get_current_player().user_id if game.get_current_player() else None}")
        logger.debug(f"Player is_current: {game.players.get(user_id).is_current if game.players.get(user_id) else 'N/A'}")

        try:
            action = ActionType(action_str)
        except ValueError:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "无效操作"}
            })
            return

        success, msg = game.execute_action(user_id, action, amount)
        logger.debug(f"Action result: success={success}, message={msg}")

        if not success:
            await websocket.send_json({
                "type": "error",
                "data": {"message": msg}
            })
            return

        # Cancel timeout after successful action
        manager.cancel_timeout(room_id)

        # Broadcast updated state
        await broadcast_game_state(room_id)

        # Check if hand ended
        if game.phase == GamePhase.ENDED:
            await handle_hand_end(room_id)


async def broadcast_room_state(room_id: int):
    """Broadcast room state to all connections using in-memory data."""
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)

    if not room:
        return

    seats = manager.get_room_seats_list(room)

    await manager.broadcast_to_room(room_id, {
        "type": "room_state",
        "data": {
            "room_id": room_id,
            "owner_id": room.owner_id,
            "status": room.status.value if hasattr(room.status, 'value') else room.status,
            "seats": seats
        }
    })


async def broadcast_game_state(room_id: int):
    """Broadcast game state to all connections."""
    game = manager.get_game(room_id)
    if game:
        # Get current phase
        current_phase = game.phase.value if hasattr(game.phase, 'value') else str(game.phase)
        last_phase = manager.last_known_phase.get(room_id)

        # Detect if we just dealt new cards (phase changed from preflop->flop, flop->turn, turn->river)
        dealing_phases = {GamePhase.FLOP.value, GamePhase.TURN.value, GamePhase.RIVER.value}
        just_dealt = (last_phase != current_phase and
                      last_phase is not None and
                      current_phase in dealing_phases)

        # Update last known phase
        manager.last_known_phase[room_id] = current_phase

        # Start timeout for current player if game is active (before getting remaining time)
        current_player = game.get_current_player()
        if current_player and game.phase not in [GamePhase.ENDED, GamePhase.SHOWDOWN]:
            if just_dealt:
                # New cards dealt - use delayed timeout (wait dealing_delay seconds before action timeout)
                manager.start_delayed_timeout(room_id, current_player.user_id, game)
            else:
                # Normal action - start timeout immediately
                manager.start_timeout(room_id, current_player.user_id, game)

        # Get remaining time for current action (after starting timeout)
        remaining_time = manager.get_remaining_time(room_id, game)

        # Send personalized state to each user
        for ws in manager.room_connections.get(room_id, []):
            user_id = manager.connection_user.get(ws)
            if user_id:
                try:
                    state = game.get_state(user_id)
                    state["room_id"] = room_id
                    state["action_timeout"] = game.action_timeout
                    state["remaining_time"] = remaining_time
                    # Add dealing_delay info for frontend display
                    if just_dealt and current_player:
                        state["dealing_delay"] = game.dealing_delay
                    await ws.send_json({
                        "type": "game_state",
                        "data": state
                    })
                except Exception as e:
                    logger.error(f"broadcast_game_state: failed to send to user {user_id}: {e}")


async def handle_timeout_fold(room_id: int, user_id: int):
    """Handle player timeout - auto fold and set to unready."""
    game = manager.get_game(room_id)
    if not game:
        return

    current_player = game.get_current_player()
    if not current_player or current_player.user_id != user_id:
        return

    logger.debug(f"Player {user_id} timed out, auto-folding")

    # Get player name before folding
    player_name = current_player.username

    # Execute fold action
    success, msg = game.execute_action(user_id, ActionType.FOLD)
    if not success:
        return

    # Set player to unready for next hand
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    if room:
        await room_service.update_seat_status(room, user_id, SeatStatus.WAITING)
        # Mark this player as wanting to stop
        manager.stop_requested[user_id] = True

    # Broadcast timeout message to chat
    await manager.broadcast_to_room(room_id, {
        "type": "chat",
        "data": {
            "user_id": 0,
            "username": "系统",
            "message": f"⏰ {player_name} 操作超时，自动弃牌",
            "is_system": True
        }
    })

    # Notify the player
    await manager.send_to_user(user_id, {
        "type": "info",
        "data": {"message": "操作超时，已自动弃牌，本局结束后将不会参与下一局"}
    })

    # Broadcast updated state
    await broadcast_game_state(room_id)

    # Check if hand ended
    if game.phase == GamePhase.ENDED:
        await handle_hand_end(room_id)


async def handle_hand_complete(room_id: int, result):
    """Handle hand completion callback."""
    # Build detailed result message
    result_lines = []

    # Get player names from result
    player_names = result.player_names or {}
    chip_changes = result.chip_changes or {}

    # Get net chips for all players from memory
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    net_chips_info = {}
    if room:
        for seat in room.seats.values():
            if seat.user_id:
                net_chips_info[seat.user_id] = seat.chips - seat.total_buyin

    # Add winner information
    for winner in result.winners:
        winner_name = player_names.get(winner["user_id"], f"玩家{winner['user_id']}")
        hand_info = f" ({winner['hand']})" if winner.get("hand") else ""
        result_lines.append(f"🏆 {winner_name} 赢得 {winner['amount']} 筹码{hand_info}")

    # Add community cards if any were dealt
    if result.community_cards and len(result.community_cards) > 0:
        result_lines.append("--- 公共牌 ---")
        cards_str = " ".join([f"{c.rank}{get_suit_symbol(c.suit)}" for c in result.community_cards])
        result_lines.append(cards_str)

    # Add showdown hands if available (only for players who showed cards)
    if result.player_hands and len(result.player_hands) > 0:
        result_lines.append("--- 开牌信息 ---")
        for uid, cards in result.player_hands.items():
            player_name = player_names.get(uid, f"玩家{uid}")
            cards_str = " ".join([f"{c.rank}{get_suit_symbol(c.suit)}" for c in cards])
            result_lines.append(f"{player_name}: {cards_str}")

    # Add chip changes for all players who participated
    if chip_changes:
        result_lines.append("--- 本局筹码变动 ---")
        for uid, change in chip_changes.items():
            if change != 0:  # Only show players with chip changes
                player_name = player_names.get(uid, f"玩家{uid}")
                if change > 0:
                    result_lines.append(f"{player_name}: +{change}")
                else:
                    result_lines.append(f"{player_name}: {change}")

    # Add net chips for all players in room
    if net_chips_info:
        result_lines.append("--- 累计净筹码 ---")
        for uid, net in net_chips_info.items():
            player_name = player_names.get(uid, f"玩家{uid}")
            if net > 0:
                result_lines.append(f"{player_name}: +{net}")
            elif net < 0:
                result_lines.append(f"{player_name}: {net}")
            else:
                result_lines.append(f"{player_name}: 0")

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
            "net_chips": net_chips_info,
            "result_message": "\n".join(result_lines)
        }
    })


def get_suit_symbol(suit: str) -> str:
    """Convert suit code to symbol."""
    symbols = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}
    return symbols.get(suit, suit)


async def _update_player_chips(game: GameEngine, room, room_service: RoomService) -> list:
    """Update seat chips from game engine. Returns list of players out of chips."""
    players_out_of_chips = []

    for player in game.players.values():
        mem_seat = manager.get_seat_by_user(room, player.user_id)
        if mem_seat:
            logger.debug(f"Player {player.user_id}: engine_chips={player.chips}, mem_chips={mem_seat.chips}")

            # Update memory - only chips, net_chips is calculated as chips - total_buyin
            await room_service.update_seat_chips(room, player.user_id, player.chips)

            # Check if player is out of chips
            if player.chips == 0:
                players_out_of_chips.append(player.user_id)

    return players_out_of_chips


async def _handle_out_of_chips(room_id: int, room, room_service: RoomService, players_out_of_chips: list):
    """Handle players who lost all chips - set them to waiting (need rebuy)."""
    for user_id in players_out_of_chips:
        await room_service.update_seat_status(room, user_id, SeatStatus.WAITING)
        # Notify the player
        await manager.send_to_user(user_id, {
            "type": "info",
            "data": {"message": "你的筹码已用完，请补充筹码后继续游戏"}
        })


async def _handle_stop_requests(game: GameEngine, room_id: int, room, room_service: RoomService, previous_hand_players: set) -> bool:
    """
    Handle players who requested to stop and owner's game stop request.
    Returns True if game should continue, False if game should end.
    """
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
        await broadcast_room_state(room_id)
        return False
    else:
        # Set players who requested to stop to waiting status
        for user_id in players_to_unready:
            await room_service.update_seat_status(room, user_id, SeatStatus.WAITING)

        # Auto-ready logic: set players who participated and have chips to READY
        auto_ready_players = []
        need_rebuy_players = []

        for user_id in previous_hand_players:
            if user_id in players_to_unready:
                continue  # Skip players who requested to stop

            mem_seat = manager.get_seat_by_user(room, user_id)
            if mem_seat:
                if mem_seat.chips > 0:
                    # Auto-ready this player
                    await room_service.update_seat_status(room, user_id, SeatStatus.READY)
                    auto_ready_players.append(user_id)
                else:
                    # Player needs rebuy
                    need_rebuy_players.append(user_id)

        # Broadcast auto-ready notification
        if auto_ready_players:
            # Get names from memory room
            auto_ready_names = []
            for uid in auto_ready_players:
                seat = manager.get_seat_by_user(room, uid)
                if seat and seat.user_name:
                    auto_ready_names.append(seat.user_name)

            if auto_ready_names:
                await manager.broadcast_to_room(room_id, {
                    "type": "chat",
                    "data": {
                        "user_id": 0,
                        "username": "系统",
                        "message": f"🔄 {', '.join(auto_ready_names)} 已自动准备",
                        "is_system": True
                    }
                })

        # Broadcast room state to update chips, net_chips, and status in frontend
        await broadcast_room_state(room_id)
        return True


async def _prepare_and_start_next_hand(game: GameEngine, room_id: int, room, room_service: RoomService, previous_hand_players: set):
    """Prepare players and start the next hand if enough players are ready."""
    # Check if we can start another hand (need at least 2 players with chips who are ready)
    # Use in-memory data
    ready_players = manager.get_ready_players(room)
    ready_count = len(ready_players)
    logger.debug(f"[AUTO-START] Checking auto-start: ready_count={ready_count}")
    for rp in ready_players:
        logger.debug(f"[AUTO-START] Ready player: user_id={rp.user_id}, chips={rp.chips}, status={rp.status}")

    if ready_count < 2:
        # Not enough players, end game
        await manager.broadcast_to_room(room_id, {
            "type": "game_ended",
            "data": {"message": "玩家不足，游戏结束"}
        })
        manager.remove_game(room_id)
        await room_service.update_room_status(room, RoomStatus.WAITING)
        for player in game.players.values():
            await room_service.update_seat_status(room, player.user_id, SeatStatus.WAITING)
        await broadcast_room_state(room_id)
        return

    # Small delay before starting next hand
    await asyncio.sleep(settings.AUTO_START_DELAY)

    # Re-fetch ready players after delay to avoid stale state
    room = await room_service.get_room_by_id(room_id)
    if not room:
        return
    ready_players = manager.get_ready_players(room)
    ready_count = len(ready_players)
    logger.debug(f"[AUTO-START] After delay, ready_count={ready_count}")

    if ready_count < 2:
        # Not enough players after delay
        await manager.broadcast_to_room(room_id, {
            "type": "game_ended",
            "data": {"message": "玩家不足，游戏结束"}
        })
        manager.remove_game(room_id)
        await room_service.update_room_status(room, RoomStatus.WAITING)
        for player in game.players.values():
            await room_service.update_seat_status(room, player.user_id, SeatStatus.WAITING)
        await broadcast_room_state(room_id)
        return

    # Remove players without chips or not ready from game
    players_to_remove = []
    for player in game.players.values():
        mem_seat = manager.get_seat_by_user(room, player.user_id)
        logger.debug(f"[AUTO-START] Checking player {player.user_id}: mem_seat exists={mem_seat is not None}, chips={mem_seat.chips if mem_seat else 'N/A'}, status={mem_seat.status if mem_seat else 'N/A'}")
        if not mem_seat or mem_seat.chips == 0 or mem_seat.status != SeatStatus.READY:
            players_to_remove.append(player.user_id)

    logger.debug(f"[AUTO-START] Players to remove (no chips): {players_to_remove}")
    for user_id in players_to_remove:
        game.remove_player(user_id)

    logger.debug(f"[AUTO-START] game.players after removal: {list(game.players.keys())}")

    # Sync chips from memory seats to game players for existing players
    # This ensures chips are correct after handle_hand_end updates
    for player in game.players.values():
        mem_seat = manager.get_seat_by_user(room, player.user_id)
        if mem_seat:
            if player.chips != mem_seat.chips:
                logger.debug(f"[AUTO-START] Syncing chips for player {player.user_id}: {player.chips} -> {mem_seat.chips}")
                player.chips = mem_seat.chips

    # Add new ready players to game (players who weren't in previous hand but are now ready)
    new_players = []
    logger.debug(f"[AUTO-START] Checking ready_players for new additions:")
    for mem_seat in ready_players:
        user_id = mem_seat.user_id
        logger.debug(f"[AUTO-START] Checking user_id={user_id}, in game.players={user_id in game.players}")
        if user_id not in game.players:
            game.add_player(user_id, mem_seat.user_name, mem_seat.seat_index, mem_seat.chips)
            new_players.append(mem_seat.user_name)
            logger.debug(f"[AUTO-START] Added new player: {mem_seat.user_name}")

    logger.debug(f"[AUTO-START] game.players after additions: {list(game.players.keys())}")

    # Notify about new players joining
    if new_players:
        await manager.broadcast_to_room(room_id, {
            "type": "chat",
            "data": {
                "user_id": 0,
                "username": "系统",
                "message": f"🆕 {', '.join(new_players)} 加入本局",
                "is_system": True
            }
        })

    # Update room status
    await room_service.update_room_status(room, RoomStatus.PLAYING)

    # Broadcast room state to update chips and net_chips in frontend
    await broadcast_room_state(room_id)

    # Reset all players in game to READY status before starting hand
    # This is necessary because reset_for_hand() only handles PLAYING/FOLDED/ALL_IN states
    from app.game.player import PlayerStatus
    logger.debug(f"[AUTO-START] Resetting player statuses before start_hand:")
    for player in game.players.values():
        logger.debug(f"[AUTO-START] Player {player.user_id}: status={player.status} -> READY")
        player.status = PlayerStatus.READY

    # Start the hand
    logger.debug(f"[AUTO-START] Calling start_hand()...")
    success = game.start_hand()
    logger.debug(f"[AUTO-START] start_hand() returned: {success}")
    if not success:
        logger.debug(f"Failed to start next hand after auto-ready")
        # Not enough players, end game
        await manager.broadcast_to_room(room_id, {
            "type": "game_ended",
            "data": {"message": "玩家不足，游戏结束"}
        })
        manager.remove_game(room_id)
        await room_service.update_room_status(room, RoomStatus.WAITING)
        for player in game.players.values():
            await room_service.update_seat_status(room, player.user_id, SeatStatus.WAITING)
        await broadcast_room_state(room_id)
        return

    # Update seat status for players in game AFTER start_hand succeeds
    for player in game.players.values():
        await room_service.update_seat_status(room, player.user_id, SeatStatus.PLAYING)

    await broadcast_game_state(room_id)

    # Check if hand ended immediately (e.g., both blinds all-in)
    if game.phase == GamePhase.ENDED:
        await handle_hand_end(room_id)


async def handle_hand_end(room_id: int):
    """Handle end of a hand."""
    game = manager.get_game(room_id)

    if not game:
        return

    logger.debug(f"handle_hand_end called for room {room_id}")
    logger.debug(f"game.phase = {game.phase}")

    # Cancel any pending timeout
    manager.cancel_timeout(room_id)

    # Track players who participated in this hand (for auto-ready)
    previous_hand_players = set(game.players.keys())

    # Update seat chips and net_chips in memory
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)

    if not room:
        return

    # Update chips and track players out of chips
    players_out_of_chips = await _update_player_chips(game, room, room_service)

    # Set room status to WAITING between hands
    await room_service.update_room_status(room, RoomStatus.WAITING)

    # Call on_hand_complete callback to broadcast results
    if game.on_hand_complete and hasattr(game, '_last_result') and game._last_result:
        logger.debug(f"Calling on_hand_complete with _last_result")
        await game.on_hand_complete(game._last_result)

    # Handle players who lost all chips
    await _handle_out_of_chips(room_id, room, room_service, players_out_of_chips)

    # Handle stop requests and check if game should continue
    game_should_continue = await _handle_stop_requests(game, room_id, room, room_service, previous_hand_players)

    if game_should_continue:
        # Prepare and start next hand
        await _prepare_and_start_next_hand(game, room_id, room, room_service, previous_hand_players)
