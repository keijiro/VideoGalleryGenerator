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
        up_link = '' if is_root else '<a href="../index.html" class="up-link">↑ Up</a>'

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
        }}

        .video-container video {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }}

        .close-button {{
            position: absolute;
            top: -40px;
            right: 0;
            background: #fff;
            border: none;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            font-size: 24px;
            cursor: pointer;
            line-height: 1;
        }}

        .close-button:hover {{
            background: #ddd;
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
            <button class="close-button" onclick="closeVideo()">×</button>
            <video id="videoPlayer" loop muted autoplay></video>
        </div>
    </div>

    <script>
        const overlay = document.getElementById('videoOverlay');
        const videoPlayer = document.getElementById('videoPlayer');
        const thumbnails = document.querySelectorAll('.thumbnail');

        thumbnails.forEach(thumb => {{
            thumb.addEventListener('click', () => {{
                const videoFile = thumb.dataset.video;
                videoPlayer.src = videoFile;
                overlay.classList.add('active');
                videoPlayer.play();
            }});
        }});

        videoPlayer.addEventListener('click', () => {{
            if (videoPlayer.paused) {{
                videoPlayer.play();
            }} else {{
                videoPlayer.pause();
            }}
        }});

        function closeVideo() {{
            overlay.classList.remove('active');
            videoPlayer.pause();
            videoPlayer.src = '';
        }}

        overlay.addEventListener('click', (e) => {{
            if (e.target === overlay) {{
                closeVideo();
            }}
        }});

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
