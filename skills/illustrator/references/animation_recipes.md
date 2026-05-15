# Animation Recipes

Animation is enabled when PyMOL or VMD AND ffmpeg are on `PATH`.
The default is 30 fps with stride 10 (every 10th frame).

PyMOL: uses `movie.produce` with `encoder=ffmpeg`. VMD: invokes the
`make movie` plugin (TBD; current implementation focuses on PyMOL).

Output formats:
- `.mp4` (default, h264 via ffmpeg)
- `.gif` (optional; set `animation.formats=["mp4","gif"]`)
