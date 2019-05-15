#!/usr/bin/env python3
"""
This file is part of pytranscoder.

Copyright (C) 2018, James Lee <jamesl33info@gmail.com>.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import queue
import subprocess
import threading

from typing import List

import pyaml
import yaml


TRANSCODE_WORKERS = 8
DEFAULT_MEDIA_DIR = '/mnt/storage/media'
DEFAULT_STORE_FILENAME = '/mnt/storage/media/pytranscoder.yml'
SUPPORTED_FILE_EXTENSIONS = ['.mp4', '.avi', '.mkv']


def get_media_files(directory: str) -> List[str]:
    mediaFiles = []

    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if os.path.splitext(filename)[-1] in SUPPORTED_FILE_EXTENSIONS:
                mediaFiles.append(os.path.join(dirpath, filename))

    return mediaFiles


class Store:
    def __init__(self, filename: str, mediaDir: str) -> None:
        self._filename = os.path.expanduser(filename)
        self._mediaDir = mediaDir

        # Open and update the store
        try:
            with open(self._filename, 'r') as infile:
                self._data = yaml.load(infile, Loader=yaml.FullLoader)
        except FileNotFoundError:
            self._data = {
                'transcoded': [],
                'untranscoded': []
            }

        # Update the store once we have opened it
        knownFiles = self._data['transcoded'] + self._data['untranscoded']
        mediaFiles = get_media_files(self._mediaDir)

        for file in mediaFiles:
            if file not in knownFiles:
                self._data['untranscoded'].append(file)

        # Check for any media files which have been deleted
        for file in self._data['transcoded'].copy():
            if file not in mediaFiles:
                self._data['transcoded'].remove(file)

        for file in self._data['untranscoded'].copy():
            if file not in mediaFiles:
                self._data['untranscoded'].remove(file)

        # Save the updated file
        self.write_to_disk()

    @property
    def transcoded(self) -> List[str]:
        return self._data['transcoded']

    @property
    def untranscoded(self) -> List[str]:
        return self._data['untranscoded']

    def mark_transcoded(self, file: str) -> None:
        self._data['untranscoded'].remove(file)
        self._data['transcoded'].append(os.path.splitext(file)[0] + '.mp4')
        self.write_to_disk()

    def write_to_disk(self) -> None:
        for key in self._data:
            self._data[key].sort()

        with open(self._filename, 'w') as outfile:
            pyaml.dump(self._data, outfile)


def transcode_worker(store: Store, transcodeQueue: queue.Queue) -> None:
    while True:
        try:
            file = transcodeQueue.get(timeout=5)
            dirname = os.path.dirname(file)
            basename = os.path.basename(file)
            filename, _ = os.path.splitext(basename)
        except queue.Empty:
            # Stop the worker if there isn't any more items to transcode
            break

        subprocess.call('ffmpeg -i file:"{0}" -map_chapters -1 -map_metadata -1 -metadata:s:a language=eng -metadata:s:v language=eng -sn -profile:v high -level:v 4.0 -acodec aac -vcodec h264 "{1}/{2}.transcoding.mp4"'.format(file, dirname, filename), shell=True)
        os.remove(file)
        os.rename(os.path.join(dirname, filename + '.transcoding.mp4'), os.path.join(dirname, filename + '.mp4'))

        store.mark_transcoded(file)
        transcodeQueue.task_done()


def transcode_files(count: int) -> None:
    store = Store(DEFAULT_STORE_FILENAME, DEFAULT_MEDIA_DIR)

    transcodeQueue = queue.Queue()

    for file in store.untranscoded[:count]:
        transcodeQueue.put(file)

    for _ in range(TRANSCODE_WORKERS):
        thread = threading.Thread(target=transcode_worker,
                                  args=(store, transcodeQueue))
        thread.setDaemon(True)
        thread.start()

    transcodeQueue.join()


if __name__ == '__main__':
    transcode_files(25)
