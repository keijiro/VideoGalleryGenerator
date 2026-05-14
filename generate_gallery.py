#!/usr/bin/env python3
"""
Media Gallery Generator
Scans directories for media files and generates static HTML galleries
"""

import html
import re
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaItem:
    path: Path
    media_type: str


class MediaGalleryGenerator:
    """Generate HTML galleries for media files"""

    THUMBS_DIR = "Thumbs"
    VIDEO_EXTENSION = ".mp4"
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
    MEDIA_EXTENSIONS = {VIDEO_EXTENSION} | IMAGE_EXTENSIONS
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
            media_items = self._find_media_items(current_dir)

            if media_items:
                print(f"Processing: {current_dir}")
                self._process_directory(current_dir, media_items)

    def _walk_directories(self, root: Path):
        """Walk through directories, yielding each one (excluding Thumbs)"""
        yield root

        for item in root.iterdir():
            if item.is_dir() and item.name != self.THUMBS_DIR:
                yield from self._walk_directories(item)

    def _find_media_items(self, directory: Path) -> list[MediaItem]:
        """Find all media files in the given directory (non-recursive)"""
        media_items = []
        for item in directory.iterdir():
            suffix = item.suffix.lower()
            if not item.is_file() or suffix not in self.MEDIA_EXTENSIONS:
                continue

            media_type = "video" if suffix == self.VIDEO_EXTENSION else "image"
            media_items.append(MediaItem(item, media_type))

        return sorted(media_items, key=lambda x: self._natural_sort_key(x.path.name))

    def _process_directory(self, directory: Path, media_items: list[MediaItem]):
        """Process a directory: generate thumbnails and HTML"""
        # Create Thumbs directory if needed
        thumbs_dir = directory / self.THUMBS_DIR
        thumbs_dir.mkdir(exist_ok=True)

        # Generate thumbnails
        for media_item in media_items:
            self._generate_thumbnail(media_item, thumbs_dir)

        # Generate HTML
        self._generate_html(directory, media_items)

    def _generate_thumbnail(self, media_item: MediaItem, thumbs_dir: Path):
        """Generate thumbnail for a media item"""
        thumb_name = self._thumbnail_name(media_item.path)
        thumb_path = thumbs_dir / thumb_name

        # Check if thumbnail needs update
        if thumb_path.exists():
            if thumb_path.stat().st_mtime >= media_item.path.stat().st_mtime:
                return  # Thumbnail is up to date

        print(f"  Creating thumbnail: {thumb_name}")

        if media_item.media_type == "video":
            self._generate_video_thumbnail(media_item.path, thumb_path, thumbs_dir)
        else:
            self._generate_image_thumbnail(media_item.path, thumb_path)

    def _generate_video_thumbnail(self, video_path: Path, thumb_path: Path, thumbs_dir: Path):
        """Generate thumbnail from first frame of video"""
        temp_thumb = thumbs_dir / f"temp_{thumb_path.name}"
        try:
            # Extract first frame
            subprocess.run([
                'ffmpeg', '-y', '-i', str(video_path),
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

    def _generate_image_thumbnail(self, image_path: Path, thumb_path: Path):
        """Generate thumbnail from an image file"""
        try:
            subprocess.run([
                'convert', str(image_path),
                '-resize', f'{self.THUMB_SIZE}x{self.THUMB_SIZE}>',
                str(thumb_path)
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"  Error generating thumbnail: {e}")

    @staticmethod
    def _thumbnail_name(media_path: Path) -> str:
        return media_path.name + ".jpg"

    def _generate_html(self, directory: Path, media_items: list[MediaItem]):
        """Generate index.html for the directory"""
        html_path = directory / "index.html"

        # Check if HTML needs update
        if html_path.exists():
            html_mtime = html_path.stat().st_mtime
            # Check if any media file is newer
            needs_update = any(
                item.path.stat().st_mtime > html_mtime for item in media_items
            )
            if not needs_update:
                return  # HTML is up to date

        print(f"  Generating index.html")

        # Determine relative path to parent
        is_root = (directory == self.root_path)

        html_content = self._create_html_content(directory, media_items, is_root)

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _create_html_content(self, directory: Path, media_items: list[MediaItem], is_root: bool) -> str:
        """Create HTML content for the gallery"""

        thumbnails_html = self._create_thumbnail_html(media_items)
        up_link = self._create_up_link(is_root)

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Media Gallery - {html.escape(directory.name)}</title>
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

        .video-frame {{
            position: relative;
            overflow: hidden;
            cursor: pointer;
            touch-action: none;
            flex: none;
        }}

        .viewer-media {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: none;
            user-select: none;
            -webkit-user-drag: none;
        }}

        .viewer-media.active {{
            display: block;
        }}

        .video-controls {{
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

        .video-controls.active {{
            display: grid;
        }}

        .video-controls.image-mode .video-only {{
            display: none;
        }}

        .video-controls.image-mode .controls-header {{
            justify-content: flex-end;
        }}

        .controls-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
        }}

        .control-row {{
            display: grid;
            grid-template-columns: 44px 1fr 72px;
            align-items: center;
            gap: 10px;
            font-size: 13px;
        }}

        .control-row input {{
            width: 100%;
        }}

        .control-button {{
            padding: 7px 14px;
            border: 1px solid rgba(255, 255, 255, 0.35);
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.16);
            color: white;
            cursor: pointer;
        }}

        .control-button:hover {{
            background: rgba(255, 255, 255, 0.26);
        }}

        .zoom-value {{
            text-align: right;
        }}

    </style>
</head>
<body>
    {up_link}

    <div class="gallery">
{thumbnails_html}
    </div>

    <div class="video-overlay" id="videoOverlay">
        <div class="video-container" id="videoContainer">
            <div class="video-frame" id="videoFrame">
                <video class="viewer-media" id="videoPlayer" loop muted autoplay></video>
                <img class="viewer-media" id="imageViewer" alt="" draggable="false">
            </div>
            <div class="video-controls" id="videoControls">
                <div class="controls-header">
                    <button class="control-button video-only" id="playToggle" type="button">Pause</button>
                    <button class="control-button" id="closeVideoButton" type="button">Close</button>
                </div>
                <div class="control-row video-only">
                    <span>A</span>
                    <input id="loopStart" type="range" min="0" max="0" step="0.01" value="0">
                    <span id="loopStartTime">00:00.00</span>
                </div>
                <div class="control-row video-only">
                    <span>B</span>
                    <input id="loopEnd" type="range" min="0" max="0" step="0.01" value="0">
                    <span id="loopEndTime">00:00.00</span>
                </div>
                <div class="control-row">
                    <span>Zoom</span>
                    <input id="zoomSlider" type="range" min="1" max="8" step="0.1" value="1">
                    <span class="zoom-value" id="zoomValue">1.0x</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        const overlay = document.getElementById('videoOverlay');
        const videoContainer = document.getElementById('videoContainer');
        const videoFrame = document.getElementById('videoFrame');
        const videoPlayer = document.getElementById('videoPlayer');
        const imageViewer = document.getElementById('imageViewer');
        const thumbnails = document.querySelectorAll('.thumbnail');
        const videoControls = document.getElementById('videoControls');
        const playToggle = document.getElementById('playToggle');
        const closeVideoButton = document.getElementById('closeVideoButton');
        const loopStartInput = document.getElementById('loopStart');
        const loopEndInput = document.getElementById('loopEnd');
        const loopStartTime = document.getElementById('loopStartTime');
        const loopEndTime = document.getElementById('loopEndTime');
        const zoomSlider = document.getElementById('zoomSlider');
        const zoomValue = document.getElementById('zoomValue');
        const minLoopSpan = 0.01;
        const clickMoveTolerance = 12;
        let loopStart = 0;
        let loopEnd = 0;
        let zoom = 1;
        let panX = 0;
        let panY = 0;
        let baseFrameWidth = 0;
        let baseFrameHeight = 0;
        let activeMediaType = 'video';
        let pointerDown = false;
        let pointerId = null;
        let pointerStartX = 0;
        let pointerStartY = 0;
        let startPanX = 0;
        let startPanY = 0;
        let pointerMoved = false;
        let pointerStartedInControls = false;

        thumbnails.forEach(thumb => {{
            thumb.addEventListener('click', () => {{
                openMedia(thumb.dataset.type, thumb.dataset.src);
            }});
        }});

        function openMedia(mediaType, mediaSrc) {{
            resetLoopState();
            resetZoomState();
            resetPointerState();
            activeMediaType = mediaType;
            videoControls.classList.toggle('image-mode', mediaType === 'image');
            videoPlayer.classList.toggle('active', mediaType === 'video');
            imageViewer.classList.toggle('active', mediaType === 'image');
            videoPlayer.pause();
            videoPlayer.src = mediaType === 'video' ? mediaSrc : '';
            imageViewer.src = mediaType === 'image' ? mediaSrc : '';
            imageViewer.alt = mediaType === 'image' ? mediaSrc : '';
            overlay.classList.add('active');
            if (mediaType === 'video') {{
                videoPlayer.play();
            }}
        }}

        function updateVideoFrameSize() {{
            const mediaSize = getActiveMediaSize();
            if (!mediaSize) {{
                videoFrame.style.width = '';
                videoFrame.style.height = '';
                baseFrameWidth = 0;
                baseFrameHeight = 0;
                return;
            }}

            const rect = videoContainer.getBoundingClientRect();
            const mediaRatio = mediaSize.width / mediaSize.height;
            const elementRatio = rect.width / rect.height;
            let frameWidth = rect.width;
            let frameHeight = rect.height;

            if (mediaRatio > elementRatio) {{
                frameHeight = rect.width / mediaRatio;
            }} else {{
                frameWidth = rect.height * mediaRatio;
            }}

            baseFrameWidth = frameWidth;
            baseFrameHeight = frameHeight;
            clampPan();
            applyZoomLayout();
        }}

        function getActiveMediaSize() {{
            if (activeMediaType === 'video') {{
                if (!videoPlayer.videoWidth || !videoPlayer.videoHeight) {{
                    return null;
                }}
                return {{ width: videoPlayer.videoWidth, height: videoPlayer.videoHeight }};
            }}

            if (!imageViewer.naturalWidth || !imageViewer.naturalHeight) {{
                return null;
            }}
            return {{ width: imageViewer.naturalWidth, height: imageViewer.naturalHeight }};
        }}

        function applyZoomLayout() {{
            const frameWidth = baseFrameWidth * zoom;
            const frameHeight = baseFrameHeight * zoom;
            videoFrame.style.width = `${{frameWidth}}px`;
            videoFrame.style.height = `${{frameHeight}}px`;
            videoFrame.style.transform = `translate(${{panX}}px, ${{panY}}px)`;
            zoomSlider.value = zoom;
            zoomValue.textContent = `${{zoom.toFixed(1)}}x`;
        }}

        function resetZoomState() {{
            zoom = 1;
            panX = 0;
            panY = 0;
            applyZoomLayout();
        }}

        function resetPointerState() {{
            if (pointerDown && pointerId !== null) {{
                try {{
                    videoFrame.releasePointerCapture(pointerId);
                }} catch (e) {{
                }}
            }}

            pointerDown = false;
            pointerId = null;
            pointerMoved = false;
        }}

        function clampPan() {{
            if (zoom <= 1 || !baseFrameWidth || !baseFrameHeight) {{
                panX = 0;
                panY = 0;
                return;
            }}

            const maxPanX = baseFrameWidth * (zoom - 1) / 2;
            const maxPanY = baseFrameHeight * (zoom - 1) / 2;
            panX = clamp(panX, -maxPanX, maxPanX);
            panY = clamp(panY, -maxPanY, maxPanY);
        }}

        videoFrame.addEventListener('pointerdown', (e) => {{
            pointerDown = true;
            pointerId = e.pointerId;
            pointerStartX = e.clientX;
            pointerStartY = e.clientY;
            startPanX = panX;
            startPanY = panY;
            pointerMoved = false;
            videoFrame.setPointerCapture(pointerId);
        }});

        videoFrame.addEventListener('pointermove', (e) => {{
            if (!pointerDown || e.pointerId !== pointerId) {{
                return;
            }}

            const dx = e.clientX - pointerStartX;
            const dy = e.clientY - pointerStartY;
            const distance = Math.hypot(dx, dy);
            pointerMoved = pointerMoved || distance >= clickMoveTolerance;

            if (zoom > 1 && pointerMoved) {{
                panX = startPanX + dx;
                panY = startPanY + dy;
                clampPan();
                applyZoomLayout();
            }}
        }});

        videoFrame.addEventListener('pointerup', (e) => {{
            if (!pointerDown || e.pointerId !== pointerId) {{
                return;
            }}

            const dx = e.clientX - pointerStartX;
            const dy = e.clientY - pointerStartY;
            const distance = Math.hypot(dx, dy);

            if (distance < clickMoveTolerance) {{
                videoControls.classList.toggle('active');
            }}

            resetPointerState();
        }});

        videoFrame.addEventListener('pointercancel', () => {{
            resetPointerState();
        }});

        videoFrame.addEventListener('click', (e) => {{
            e.stopPropagation();
        }});

        function closeVideo() {{
            overlay.classList.remove('active');
            videoPlayer.pause();
            videoPlayer.src = '';
            imageViewer.src = '';
            imageViewer.alt = '';
            videoPlayer.classList.remove('active');
            imageViewer.classList.remove('active');
            videoControls.classList.remove('image-mode');
            activeMediaType = 'video';
            resetLoopState();
            resetZoomState();
            resetPointerState();
        }}

        function resetLoopState() {{
            loopStart = 0;
            loopEnd = 0;
            videoControls.classList.remove('active');
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
            if (pointerStartedInControls) {{
                pointerStartedInControls = false;
                return;
            }}

            if (e.target === overlay || e.target === videoContainer) {{
                closeVideo();
            }}
        }});

        videoControls.addEventListener('pointerdown', () => {{
            pointerStartedInControls = true;
        }});

        videoControls.addEventListener('click', (e) => {{
            e.stopPropagation();
            pointerStartedInControls = false;
        }});

        playToggle.addEventListener('click', () => {{
            if (activeMediaType !== 'video') {{
                return;
            }}

            if (videoPlayer.paused) {{
                videoPlayer.play();
            }} else {{
                videoPlayer.pause();
            }}
        }});

        closeVideoButton.addEventListener('click', closeVideo);

        loopStartInput.addEventListener('input', () => {{
            const duration = videoPlayer.duration || 0;
            const maxStart = Math.max(0, loopEnd - minLoopSpan);
            loopStart = clamp(Number(loopStartInput.value), 0, maxStart);
            videoPlayer.currentTime = loopStart;
            updateLoopInputs(duration);
        }});

        loopEndInput.addEventListener('input', () => {{
            const duration = videoPlayer.duration || 0;
            const minEnd = Math.min(duration, loopStart + minLoopSpan);
            loopEnd = clamp(Number(loopEndInput.value), minEnd, duration);
            videoPlayer.currentTime = clamp(loopEnd - 0.5, loopStart, duration);
            updateLoopInputs(duration);
        }});

        zoomSlider.addEventListener('input', () => {{
            zoom = Number(zoomSlider.value);
            clampPan();
            applyZoomLayout();
        }});

        videoPlayer.addEventListener('loadedmetadata', () => {{
            loopStart = 0;
            loopEnd = videoPlayer.duration || 0;
            updateLoopInputs(loopEnd);
            resetZoomState();
            updateVideoFrameSize();
        }});

        imageViewer.addEventListener('load', () => {{
            resetZoomState();
            updateVideoFrameSize();
        }});

        imageViewer.addEventListener('dragstart', (e) => {{
            e.preventDefault();
        }});

        videoPlayer.addEventListener('timeupdate', () => {{
            if (loopEnd > loopStart && videoPlayer.currentTime >= loopEnd) {{
                videoPlayer.currentTime = loopStart;
                videoPlayer.play();
            }}
        }});

        videoPlayer.addEventListener('play', updatePlayToggle);
        videoPlayer.addEventListener('pause', updatePlayToggle);
        window.addEventListener('resize', updateVideoFrameSize);

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') {{
                closeVideo();
            }}
        }});
    </script>
</body>
</html>'''

    def _create_thumbnail_html(self, media_items: list[MediaItem]) -> str:
        """Create thumbnail grid items"""
        thumbnail_items = []
        for media_item in media_items:
            thumb_name = self._thumbnail_name(media_item.path)
            thumb_path = html.escape(f"{self.THUMBS_DIR}/{thumb_name}", quote=True)
            media_name = html.escape(media_item.path.name, quote=True)
            media_type = html.escape(media_item.media_type, quote=True)

            thumbnail_items.append(f'''
        <div class="thumbnail" data-type="{media_type}" data-src="{media_name}">
            <img src="{thumb_path}" alt="{media_name}">
            <div class="filename">{media_name}</div>
        </div>''')

        return '\n'.join(thumbnail_items)

    @staticmethod
    def _create_up_link(is_root: bool) -> str:
        """Create the parent directory link"""
        return '' if is_root else '<a href=".." class="up-link">↑ Up</a>'


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        target_path = "."

    try:
        generator = MediaGalleryGenerator(target_path)
        print(f"Scanning: {generator.root_path}")
        generator.scan_and_generate()
        print("Done!")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
