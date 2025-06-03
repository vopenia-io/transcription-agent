import asyncio
import uuid

from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import WorkerOptions, WorkerPermissions, cli

from livekit.agents.stt import SpeechEventType, SpeechEvent
from typing import AsyncIterable
from livekit.plugins import gladia

load_dotenv(dotenv_path='.env.local')

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    
    stt_impl = gladia.STT(
      languages=["fr"],
      translation_enabled=True,
      interim_results=False,
      translation_target_languages=["fr", "en"],
      energy_filter=False
    )
    stt_stream = stt_impl.stream()

    room = ctx.room
    
    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.RemoteTrack, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        print(f"Subscribed to track: {track.name}")
        asyncio.create_task(process_track(track, participant))

    async def process_track(track: rtc.RemoteTrack, participant: rtc.RemoteParticipant):

        audio_stream = rtc.AudioStream(track)

        async with asyncio.TaskGroup() as tg:
            # Create task for processing STT stream
            stt_task = tg.create_task(process_stt_stream(stt_stream, participant, track))

            # Process audio stream
            async for audio_event in audio_stream:
                stt_stream.push_frame(audio_event.frame)

            # Indicates the end of the audio stream
            stt_stream.end_input()

            # Wait for STT processing to complete
            await stt_task

    async def process_stt_stream(stream: AsyncIterable[SpeechEvent], participant: rtc.Participant, track: rtc.RemoteTrack):

        try:
            # Creating writer
            # writer = await room.local_participant.stream_text(
            #   topic="transcription",
            #   attributes={
            #       "lk.transcribed_track_id": track.sid,
            #       "lk.transcribed_participant_id": participant.identity
            #   }
            # )

            async for event in stream:
                if event.type == SpeechEventType.FINAL_TRANSCRIPT:
                    print(f"Final transcript: {event.alternatives[0].text}")
                    #await writer.write(event.alternatives[0].text)
                    await room.local_participant.send_text(
                      topic="lk.transcription",
                      attributes={
                          "lk.segment_id": str(uuid.uuid4()),
                          "lk.transcribed_track_id": track.sid,
                          "lk.transcribed_participant_id": participant.identity,
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
            # await writer.aclose()


if __name__ == "__main__":
  cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, permissions=WorkerPermissions(
      can_publish=True,
      can_subscribe=True,
      can_publish_data=True,
      # when set to true, the agent won't be visible to others in the room.
      # when hidden, it will also not be able to publish tracks to the room as it won't be visible.
      hidden=True,
  )))