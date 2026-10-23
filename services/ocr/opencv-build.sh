#!/usr/bin/env bash
set -Eeuo pipefail
export ENABLE_CONTRIB=1 ENABLE_HEADLESS=0 CMAKE_BUILD_PARALLEL_LEVEL=4
# Keep PaddleX's import/API surface, but do not ship unused video/network/GUI codecs.
# OpenCV 4.10's required Python typing aliases reference G-API and DNN's real classes.
export CMAKE_ARGS='-DWITH_FFMPEG=OFF -DWITH_GSTREAMER=OFF -DVIDEOIO_ENABLE_PLUGINS=OFF -DWITH_V4L=OFF -DWITH_QT=OFF -DWITH_GTK=OFF -DWITH_OPENGL=OFF -DWITH_IPP=OFF -DWITH_OPENCL=OFF -DWITH_TIFF=ON -DBUILD_TIFF=OFF -DWITH_PNG=ON -DBUILD_PNG=OFF -DWITH_JPEG=ON -DBUILD_JPEG=OFF -DWITH_OPENEXR=OFF -DWITH_WEBP=OFF -DWITH_OPENJPEG=OFF -DWITH_JASPER=OFF -DBUILD_LIST=core,imgproc,imgcodecs,calib3d,features2d,flann,photo,videoio,gapi,dnn,python3 -DBUILD_TESTS=OFF -DBUILD_PERF_TESTS=OFF -DBUILD_EXAMPLES=OFF'
python -m pip wheel --require-hashes --no-deps --no-build-isolation \
  --no-binary=opencv-contrib-python --wheel-dir=/wheelhouse -r /build/requirements.lock
python /build/wheel_manifest.py /build/requirements.lock /wheelhouse > /wheelhouse/requirements.lock
