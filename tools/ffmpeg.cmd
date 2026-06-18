@echo off
py -3.12 -c "import imageio_ffmpeg, subprocess, sys; raise SystemExit(subprocess.call([imageio_ffmpeg.get_ffmpeg_exe(), *sys.argv[1:]]))" %*
