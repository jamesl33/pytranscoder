#!/usr/bin/env python3

import os
import subprocess

from typing import List

import yaml
import pyaml
import pprint


DEFAULT_MEDIA_DIR = '/mnt/storage/media'
DEFAULT_STORE_FILENAME = '~/.pytranscoder.yml'
SUPPORTED_FILE_EXTENSIONS = ['.mp4', '.avi', '.mkv']


def get_media_files(directory: str) -> List[str]:
    mediaFiles = []

    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if os.path.splitext(filename)[-1] in SUPPORTED_FILE_EXTENSIONS:
                mediaFiles.append(os.path.join(dirpath, filename))

    return mediaFiles


class Store:
    def __init__(self, mediaDir: str) -> None:
        self.mediaDir = mediaDir

    @property
    def transcoded(self) -> List[str]:
        return self._data['transcoded']

    @property
    def untranscoded(self) -> List[str]:
        return self._data['untranscoded']

    def open(self, filename: str) -> None:
        try:
            with open(filename, 'r') as file:
                self._data = yaml.load(file)
        except FileNotFoundError:
            self._data = {
                'transcoded': [],
                'untranscoded': []
            }

    def close(self, filename: str) -> None:
        with open(filename, 'w') as file:
            pyaml.dump(self._data, file)

    def update(self) -> None:
        knownFiles = self._data['transcoded'] + self._data['untranscoded']
        mediaFiles = get_media_files(self.mediaDir)

        for file in mediaFiles:
            if file not in knownFiles:
                self._data['untranscoded'].append(file)

    def mark_transcoded(self, file: str) -> None:
        self._data['untranscoded'].remove(file)
        self._data['transcoded'].append(file)

    def __repr__(self):
        return pprint.pformat(self._data)


def transcode(count):
    store = Store(DEFAULT_MEDIA_DIR)
    store.open(os.path.expanduser(DEFAULT_STORE_FILENAME))
    store.update()

    for file in store.untranscoded[:count]:
        subprocess.call('ffmpeg -i "{0}" -map_chapters -1 -map_metadata -1 -metadata:s:a language=eng -metadata:s:v language=eng -sn -profile:v high -level:v 4.0 -acodec aac -vcodec h264 "$(dirname \"{0}\")/$(basename \"{0}\" .mp4).transcoding.mp4"'.format(file), shell=True)
        subprocess.call('rm "{0}'.format(file), shell=True)
        subprocess.call('mv "$(dirname \"{0}\")/$(basename \"{0}\" .mp4).transcoding.mp4" "{0}"'.format(file), shell=True)
        store.mark_transcoded(file)

    store.close(os.path.expanduser(DEFAULT_STORE_FILENAME))


if __name__ == '__main__':
    transcode(25)
