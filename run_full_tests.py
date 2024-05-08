#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import shutil

from tests.const import DOCKER_IMAGE


class InTempDir:
    def __init__(self, suffix="", prefix="tmp", delete=True):
        self.delete = delete
        self.temp_path = tempfile.mkdtemp(suffix=suffix, prefix=prefix)

    def __enter__(self):
        self.orig_path = os.getcwd()
        os.chdir(self.temp_path)
        return self

    def __exit__(self, *exc_info):
        # Restore the working dir and cleanup the temp one
        os.chdir(self.orig_path)
        if self.delete:
            shutil.rmtree(self.temp_path)


def test1():
    with InTempDir(prefix="scuba-systest"):
        with open(".scuba.yml", "w+t") as f:
            f.write(f"image: {DOCKER_IMAGE}\n")

        in_data = "success"

        with open("file.in", "w+t") as f:
            f.write(in_data)

        subprocess.check_call(["scuba", "/bin/sh", "-c", "cat file.in >> file.out"])
        subprocess.check_call(["scuba", "/bin/sh", "-c", "yes '' | echo 'test'"])

        with open("file.out", "rt") as f:
            out_data = f.read()

        assert in_data == out_data


def main():
    test1()
    print("All is good.")


if __name__ == "__main__":
    main()
