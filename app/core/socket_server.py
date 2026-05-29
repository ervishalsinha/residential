import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio)


async def emit_event(event: str, payload: dict, room: str | None = None) -> None:
    await sio.emit(event, payload, room=room)
