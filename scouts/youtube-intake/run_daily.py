import datetime
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

import config
import rss
import ledger
import transcript
import synthesize
import notion_writer
import thesis_updater


def process_channel(channel: "config.Channel", led: "ledger.Ledger") -> list[dict]:
    entries = rss.fetch_recent_videos(channel)
    groups = ledger.group_new_videos(entries, led)
    summaries = []

    for (channel_name, date), videos in groups.items():
        try:
            real_content_videos = []
            filtered_out = []
            for video in videos:
                result = transcript.get_transcript(video.video_id)
                if result.text is None:
                    led.mark_processed(video.video_id, "", channel=channel_name, date=date)  # flagged/skipped, don't retry forever
                    continue
                classification = synthesize.classify_video(video.title, result.text)
                if classification.has_real_content:
                    real_content_videos.append({
                        "title": video.title, "video_id": video.video_id, "transcript": result.text,
                    })
                else:
                    filtered_out.append({"title": video.title, "reason": classification.reason})
                    led.mark_processed(video.video_id, "", channel=channel_name, date=date)

            if not real_content_videos:
                continue

            if channel.format == "episode":
                for v in real_content_videos:
                    summary_md = synthesize.write_episode_summary(v["title"], channel_name, v["transcript"])
                    url = notion_writer.create_episode_page(
                        v["title"], channel_name, date, summary_md, v["video_id"], v["transcript"]
                    )
                    led.mark_processed(v["video_id"], url, channel=channel_name, date=date)
                    summaries.append({"one_liner": f"{channel_name}: {v['title']} -> {url}", "content": summary_md})
            else:
                summary_md = synthesize.write_digest_summary(channel_name, date, real_content_videos, filtered_out)
                url = notion_writer.create_digest_page(channel_name, date, summary_md, real_content_videos)
                for v in real_content_videos:
                    led.mark_processed(v["video_id"], url, channel=channel_name, date=date)
                summaries.append({
                    "one_liner": f"{channel_name} digest ({date}): {len(real_content_videos)} video(s) -> {url}",
                    "content": summary_md,
                })
        except Exception as exc:
            logging.warning(
                "synthesis/write failed for %s (%s): %s", channel_name, date, exc
            )
            summaries.append({
                "one_liner": f"{channel_name} ({date}): synthesis/write FAILED - {exc}",
                "content": "",
            })

    return summaries


def main() -> None:
    led = ledger.Ledger.load()
    all_entries: list[dict] = []

    for channel in config.CHANNELS:
        try:
            all_entries.extend(process_channel(channel, led))
        except Exception as exc:
            all_entries.append({"one_liner": f"{channel.name}: RUN FAILED - {exc}", "content": ""})

    today = datetime.date.today()
    if not all_entries:
        thesis_updater.append_archive_entry(today, "No new content across any of the 4 channels today.")
        return

    run_summary = "\n".join(e["one_liner"] for e in all_entries)

    content_summaries = [e["content"] for e in all_entries if e["content"]]
    if content_summaries:
        try:
            current_thesis = thesis_updater.fetch_page_plain_text(config.THESIS_PAGE_ID)
            material_update = thesis_updater.assess_materiality(content_summaries, current_thesis)
            if material_update:
                run_summary += (
                    "\n\n**MATERIAL UPDATE FLAGGED (needs a manual Snapshot/Operating Thesis rewrite):**\n"
                    + material_update
                )
        except Exception as exc:
            logging.warning("materiality check failed: %s", exc)
            run_summary += f"\n\n**MATERIALITY CHECK FAILED (not assessed this run):** {exc}"

    thesis_updater.append_archive_entry(today, run_summary)


if __name__ == "__main__":
    main()
