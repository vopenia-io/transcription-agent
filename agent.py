from pathlib import Path
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, WorkerPermissions, RoomInputOptions, RoomOutputOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import gladia
import datetime

load_dotenv(dotenv_path='.env.local')

async def entrypoint(ctx: JobContext):
    
    await ctx.connect()
    session = AgentSession(
        turn_detection="stt"
      # room_input_options=RoomInputOptions(
      #   text_enabled=False # disable text input
      # ), 
      # room_output_options=RoomOutputOptions(
      #   audio_enabled=False # disable audio output
      # )
    )
    
    @session.on("user_input_transcribed")
    def on_transcript(transcript):
        if transcript:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("user_speech_log.txt", "a") as f:
                f.write(f"[{timestamp}] {transcript.transcript}\n") 

    await session.start(
        agent=Agent(
            instructions="You are a helpful assistant that transcribes user speech to text.",
            stt=gladia.STT(
                languages=["nl", "fr", "en", "de"],
                translation_enabled=True,
                interim_results=True,
                translation_target_languages=["fr"]
            )
        ),
        room=ctx.room
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, permissions=WorkerPermissions(
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
        # when set to true, the agent won't be visible to others in the room.
        # when hidden, it will also not be able to publish tracks to the room as it won't be visible.
        hidden=True,
    )))