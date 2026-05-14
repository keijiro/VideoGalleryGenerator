#!/usr/bin/env python3
"""
Video Gallery Generator
Scans directories for mp4 files and generates static HTML galleries
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List


class VideoGalleryGenerator:
    """Generate HTML galleries for video files"""

    THUMBS_DIR = "Thumbs"
    VIDEO_EXTENSION = ".mp4"
    THUMB_SIZE = 200

    @staticmethod
    def _natural_sort_key(text: str):
        """Generate a key for natural sorting (numeric-aware)"""
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {root_path}")

    def scan_and_generate(self):
        """Scan directories recursively and generate galleries"""
        for current_dir in self._walk_directories(self.root_path):
            mp4_files = self._find_mp4_files(current_dir)

            if mp4_files:
                print(f"Processing: {current_dir}")
                self._process_directory(current_dir, mp4_files)

    def _walk_directories(self, root: Path):
        """Walk through directories, yielding each one (excluding Thumbs)"""
        yield root

        for item in root.iterdir():
            if item.is_dir() and item.name != self.THUMBS_DIR:
                yield from self._walk_directories(item)

    def _find_mp4_files(self, directory: Path) -> List[Path]:
        """Find all mp4 files in the given directory (non-recursive)"""
        mp4_files = []
        for item in directory.iterdir():
            if item.is_file() and item.suffix.lower() == self.VIDEO_EXTENSION:
                mp4_files.append(item)
        return sorted(mp4_files, key=lambda x: self._natural_sort_key(x.name))

    def _process_directory(self, directory: Path, mp4_files: List[Path]):
        """Process a directory: generate thumbnails and HTML"""
        # Create Thumbs directory if needed
        thumbs_dir = directory / self.THUMBS_DIR
        thumbs_dir.mkdir(exist_ok=True)

        # Generate thumbnails
        for mp4_file in mp4_files:
            self._generate_thumbnail(mp4_file, thumbs_dir)

        # Generate HTML
        self._generate_html(directory, mp4_files)

    def _generate_thumbnail(self, mp4_file: Path, thumbs_dir: Path):
        """Generate thumbnail from first frame of video"""
        thumb_name = mp4_file.stem + ".jpg"
        thumb_path = thumbs_dir / thumb_name

        # Check if thumbnail needs update
        if thumb_path.exists():
            if thumb_path.stat().st_mtime >= mp4_file.stat().st_mtime:
                return  # Thumbnail is up to date

        print(f"  Creating thumbnail: {thumb_name}")

        # Extract first frame with ffmpeg
        temp_thumb = thumbs_dir / f"temp_{thumb_name}"
        try:
            # Extract first frame
            subprocess.run([
                'ffmpeg', '-y', '-i', str(mp4_file),
                '-vframes', '1',
                '-f', 'image2',
                str(temp_thumb)
            ], check=True, capture_output=True)

            # Resize with ImageMagick (convert)
            subprocess.run([
                'convert', str(temp_thumb),
                '-resize', f'{self.THUMB_SIZE}x{self.THUMB_SIZE}>',
                str(thumb_path)
            ], check=True, capture_output=True)

            # Remove temp file
            if temp_thumb.exists():
                temp_thumb.unlink()

        except subprocess.CalledProcessError as e:
            print(f"  Error generating thumbnail: {e}")
            if temp_thumb.exists():
                temp_thumb.unlink()

    def _generate_html(self, directory: Path, mp4_files: List[Path]):
        """Generate index.html for the directory"""
        html_path = directory / "index.html"

        # Check if HTML needs update
        if html_path.exists():
            html_mtime = html_path.stat().st_mtime
            # Check if any mp4 file is newer
            needs_update = any(
                mp4.stat().st_mtime > html_mtime for mp4 in mp4_files
            )
            if not needs_update:
                return  # HTML is up to date

        print(f"  Generating index.html")

        # Determine relative path to parent
        is_root = (directory == self.root_path)

        html_content = self._create_html_content(directory, mp4_files, is_root)

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _create_html_content(self, directory: Path, mp4_files: List[Path], is_root: bool) -> str:
        """Create HTML content for the gallery"""

        # Create thumbnail items
        thumbnail_items = []
        for mp4_file in mp4_files:
            thumb_name = mp4_file.stem + ".jpg"
            thumb_path = f"{self.THUMBS_DIR}/{thumb_name}"
            video_name = mp4_file.name

            thumbnail_items.append(f'''
        <div class="thumbnail" data-video="{video_name}">
            <img src="{thumb_path}" alt="{video_name}">
            <div class="filename">{video_name}</div>
        </div>''')

        thumbnails_html = '\n'.join(thumbnail_items)

        # Up link (show only if not root)
        up_link = '' if is_root else '<a href=".." class="up-link">↑ Up</a>'

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Gallery - {directory.name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: Arial, sans-serif;
            padding: 20px;
            background: #f0f0f0;
        }}

        .up-link {{
            display: inline-block;
            padding: 10px 20px;
            background: #333;
            color: white;
            text-decoration: none;
            margin-bottom: 20px;
            border-radius: 4px;
        }}

        .up-link:hover {{
            background: #555;
        }}

        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
        }}

        .thumbnail {{
            background: white;
            padding: 10px;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s;
        }}

        .thumbnail:hover {{
            transform: scale(1.05);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}

        .thumbnail img {{
            width: 100%;
            height: auto;
            display: block;
            border-radius: 4px;
        }}

        .filename {{
            margin-top: 8px;
            font-size: 12px;
            color: #666;
            word-break: break-all;
        }}

        .video-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}

        .video-overlay.active {{
            display: flex;
        }}

        .video-container {{
            position: relative;
            width: 90vw;
            height: 90vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}

        .video-container video {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            display: block;
        }}

        .loop-controls {{
            display: none;
            position: absolute;
            top: 60%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: min(560px, 82vw);
            padding: 14px 16px;
            background: rgba(0, 0, 0, 0.58);
            color: white;
            border-radius: 8px;
            backdrop-filter: blur(8px);
            gap: 10px;
        }}

        .loop-controls.active {{
            display: grid;
        }}

        .loop-row {{
            display: grid;
            grid-template-columns: 44px 1fr 72px;
            align-items: center;
            gap: 10px;
            font-size: 13px;
        }}

        .loop-row input {{
            width: 100%;
        }}

        .play-toggle {{
            justify-self: start;
            padding: 7px 14px;
            border: 1px solid rgba(255, 255, 255, 0.35);
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.16);
            color: white;
            cursor: pointer;
        }}

        .play-toggle:hover {{
            background: rgba(255, 255, 255, 0.26);
        }}

    </style>
</head>
<body>
    {up_link}

    <div class="gallery">
{thumbnails_html}
    </div>

    <div class="video-overlay" id="videoOverlay">
        <div class="video-container">
            <video id="videoPlayer" loop muted autoplay></video>
            <div class="loop-controls" id="loopControls">
                <button class="play-toggle" id="playToggle" type="button">Pause</button>
                <div class="loop-row">
                    <span>A</span>
                    <input id="loopStart" type="range" min="0" max="0" step="0.01" value="0">
                    <span id="loopStartTime">00:00.00</span>
                </div>
                <div class="loop-row">
                    <span>B</span>
                    <input id="loopEnd" type="range" min="0" max="0" step="0.01" value="0">
                    <span id="loopEndTime">00:00.00</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        const overlay = document.getElementById('videoOverlay');
        const videoPlayer = document.getElementById('videoPlayer');
        const thumbnails = document.querySelectorAll('.thumbnail');
        const loopControls = document.getElementById('loopControls');
        const playToggle = document.getElementById('playToggle');
        const loopStartInput = document.getElementById('loopStart');
        const loopEndInput = document.getElementById('loopEnd');
        const loopStartTime = document.getElementById('loopStartTime');
        const loopEndTime = document.getElementById('loopEndTime');
        const minLoopSpan = 0.01;
        let loopStart = 0;
        let loopEnd = 0;

        thumbnails.forEach(thumb => {{
            thumb.addEventListener('click', () => {{
                const videoFile = thumb.dataset.video;
                resetLoopState();
                videoPlayer.src = videoFile;
                overlay.classList.add('active');
                videoPlayer.play();
            }});
        }});

        function isInsideVideoContent(e) {{
            const rect = videoPlayer.getBoundingClientRect();
            if (!videoPlayer.videoWidth || !videoPlayer.videoHeight) {{
                return true;
            }}

            const videoRatio = videoPlayer.videoWidth / videoPlayer.videoHeight;
            const elementRatio = rect.width / rect.height;
            let contentWidth = rect.width;
            let contentHeight = rect.height;

            if (videoRatio > elementRatio) {{
                contentHeight = rect.width / videoRatio;
            }} else {{
                contentWidth = rect.height * videoRatio;
            }}

            const contentLeft = rect.left + (rect.width - contentWidth) / 2;
            const contentTop = rect.top + (rect.height - contentHeight) / 2;
            const x = e.clientX;
            const y = e.clientY;

            return x >= contentLeft &&
                   x <= contentLeft + contentWidth &&
                   y >= contentTop &&
                   y <= contentTop + contentHeight;
        }}

        videoPlayer.addEventListener('click', (e) => {{
            if (!isInsideVideoContent(e)) {{
                closeVideo();
                return;
            }}

            loopControls.classList.toggle('active');
        }});

        function closeVideo() {{
            overlay.classList.remove('active');
            videoPlayer.pause();
            videoPlayer.src = '';
            resetLoopState();
        }}

        function resetLoopState() {{
            loopStart = 0;
            loopEnd = 0;
            loopControls.classList.remove('active');
            updateLoopInputs(0);
            updatePlayToggle();
        }}

        function updateLoopInputs(duration) {{
            loopStartInput.max = duration;
            loopEndInput.max = duration;
            loopStartInput.value = loopStart;
            loopEndInput.value = loopEnd;
            loopStartTime.textContent = formatTime(loopStart);
            loopEndTime.textContent = formatTime(loopEnd);
        }}

        function formatTime(seconds) {{
            const safeSeconds = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
            const minutes = Math.floor(safeSeconds / 60);
            const remaining = safeSeconds - minutes * 60;
            return `${{String(minutes).padStart(2, '0')}}:${{remaining.toFixed(2).padStart(5, '0')}}`;
        }}

        function clamp(value, min, max) {{
            return Math.min(Math.max(value, min), max);
        }}

        function updatePlayToggle() {{
            playToggle.textContent = videoPlayer.paused ? 'Play' : 'Pause';
        }}

        overlay.addEventListener('click', (e) => {{
            if (e.target !== videoPlayer) {{
                closeVideo();
            }}
        }});

        loopControls.addEventListener('click', (e) => {{
            e.stopPropagation();
        }});

        playToggle.addEventListener('click', () => {{
            if (videoPlayer.paused) {{
                videoPlayer.play();
            }} else {{
                videoPlayer.pause();
            }}
        }});

        loopStartInput.addEventListener('input', () => {{
            const duration = videoPlayer.duration || 0;
            const maxStart = Math.max(0, loopEnd - minLoopSpan);
            loopStart = clamp(Number(loopStartInput.value), 0, maxStart);
            if (videoPlayer.currentTime < loopStart || videoPlayer.currentTime >= loopEnd) {{
                videoPlayer.currentTime = loopStart;
            }}
            updateLoopInputs(duration);
        }});

        loopEndInput.addEventListener('input', () => {{
            const duration = videoPlayer.duration || 0;
            const minEnd = Math.min(duration, loopStart + minLoopSpan);
            loopEnd = clamp(Number(loopEndInput.value), minEnd, duration);
            if (videoPlayer.currentTime >= loopEnd) {{
                videoPlayer.currentTime = loopStart;
            }}
            updateLoopInputs(duration);
        }});

        videoPlayer.addEventListener('loadedmetadata', () => {{
            loopStart = 0;
            loopEnd = videoPlayer.duration || 0;
            updateLoopInputs(loopEnd);
        }});

        videoPlayer.addEventListener('timeupdate', () => {{
            if (loopEnd > loopStart && videoPlayer.currentTime >= loopEnd) {{
                videoPlayer.currentTime = loopStart;
                videoPlayer.play();
            }}
        }});

        videoPlayer.addEventListener('play', updatePlayToggle);
        videoPlayer.addEventListener('pause', updatePlayToggle);

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') {{
                closeVideo();
            }}
        }});
    </script>
</body>
</html>'''


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        target_path = "."

    try:
        generator = VideoGalleryGenerator(target_path)
        print(f"Scanning: {generator.root_path}")
        generator.scan_and_generate()
        print("Done!")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
