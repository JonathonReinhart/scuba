import os

class FileCleanup(object):
    def __init__(self):
        self._files = []

    def register(self, path):
        '''Register a file to be removed at exit'''
        self._files.append(path)

    @property
    def files(self):
        '''Get files registered for cleanup'''
        return iter(self._files)

    def cleanup(self):
        '''Cleanup registered files'''

        for f in self._files:
            try:
                os.remove(f)
            except OSError:
                pass

        self._files = []
