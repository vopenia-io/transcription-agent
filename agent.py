import asyncio
import uuid

from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import WorkerOptions, WorkerPermissions, cli
from livekit.agents.voice import Agent, AgentSession

from livekit.agents.stt import SpeechEventType, SpeechEvent
from typing import AsyncIterable
from livekit.plugins import gladia

load_dotenv(dotenv_path='.env.local')

class TranscriptionAgent():
    def __init__(self, room):
        self._room = room
        self._stt = gladia.STT(
            languages=["fr"],
            translation_enabled=True,
            interim_results=False,
            translation_target_languages=["fr", "en", "de", "nl"],
            energy_filter=False
        )
    
    # def start(self):
    #     self._room.on("track_subscribed", self._on_track_subscribed)

    def _on_track_subscribed(self, track: rtc.RemoteTrack, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        print("Subscribed to track: {track.name}")
        if (self._room.local_participant.identity != participant.identity and isinstance(track, rtc.RemoteAudioTrack)):
            asyncio.create_task(self._process_track(track, participant))

    async def _process_track(self, track: rtc.RemoteTrack, participant: rtc.RemoteParticipant):
        stt_stream = self._stt.stream()
        audio_stream = rtc.AudioStream(track)
        
        async with asyncio.TaskGroup() as tg:
            # Create task for processing STT stream
            stt_task = tg.create_task(self._process_stt_stream(stt_stream, participant, track))

            # Process audio stream
            async for audio_event in audio_stream:
                stt_stream.push_frame(audio_event.frame)

            # Indicates the end of the audio stream
            stt_stream.end_input()

            # Wait for STT processing to complete
            await stt_task

    async def _process_stt_stream(self, stream: AsyncIterable[SpeechEvent], participant: rtc.Participant, track: rtc.RemoteTrack):
        async for event in stream:
            try:
                if event.type == SpeechEventType.FINAL_TRANSCRIPT:
                    print(f"Final transcript: {event.alternatives[0].text}")
                    #await writer.write(event.alternatives[0].text)
                    await self._room.local_participant.send_text(
                        topic="lk.transcription",
                        attributes={
                            "lk.segment_id": str(uuid.uuid4()),
                            "lk.transcribed_track_id": track.sid,
                            "lk.transcribed_participant_id": participant.identity,
                            "lk.transcribed_participant_name": participant.name,
                            "lk.language": event.alternatives[0].language
                        },
                        text=event.alternatives[0].text
                    )
                elif event.type == SpeechEventType.INTERIM_TRANSCRIPT:
                    print(f"Interim transcript: {event.alternatives[0].text}")
                elif event.type == SpeechEventType.START_OF_SPEECH:
                    print("Start of speech")
                elif event.type == SpeechEventType.END_OF_SPEECH:
                    print("End of speech")
            finally:
                await stream.aclose()

async def entrypoint(ctx: agents.JobContext):
    print("entrypoint")
    await ctx.connect()
    agent = TranscriptionAgent(ctx.room)

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.RemoteTrack, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        agent._on_track_subscribed(track, publication, participant)

if __name__ == "__main__":
  cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, permissions=WorkerPermissions(
      can_publish=True,
      can_subscribe=True,
      can_publish_data=True,
      # when set to true, the agent won't be visible to others in the room.
      # when hidden, it will also not be able to publish tracks to the room as it won't be visible.
      hidden=False,
  )))