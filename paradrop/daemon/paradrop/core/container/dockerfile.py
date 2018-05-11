"""
This module generates a Dockerfile for use with light chutes.
"""

import platform
import re

from io import BytesIO


class Dockerfile(object):
    requiredFields = ["image", "command"]

    def __init__(self, service):
        """
        service: Service object containing configuration for the image.
        """
        self.service = service

    def getBytesIO(self):
        """
        Geterate a Dockerfile and return as a BytesIO object.
        """
        data = self.getString()
        return BytesIO(data.encode("utf-8"))

    def getString(self):
        """
        Generate a Dockerfile as a multi-line string.
        """
        # Required fields for generating Dockerfile.
        # Developer tells us what language pack to use and what command to run.
        language = self.service.image
        command = self.service.command

        # Extra build options.
        build = self.service.build
        image_source = build.get("image_source", "paradrop")
        image_version = build.get("image_version", "latest")
        packages = build.get("packages", [])

        as_root = self.service.requests.get("as-root", False)

        # Example base image: paradrop/node-x86_64:latest
        from_image = "{}/{}-{}:{}".format(image_source, language,
                platform.machine(), image_version)

        if isinstance(command, basestring):
            cmd_string = command
        elif isinstance(command, list):
            cmd_string = "[{}]".format(",".join(
                "\"{}\"".format(v) for v in command))
        else:
            raise Exception("command must be either a string or list of strings")

        dockerfile = "FROM {}\n".format(from_image)
        if len(packages) > 0:
            # The base images set up an unprivileged user, paradrop.  We will
            # need to run as root to install packages, though.
            dockerfile += "USER root\n"
            dockerfile += "RUN apt-get update && apt-get install -y {}\n".format(
                    " ".join(packages))
            # Drop back to user paradrop after installing packages.
            if not as_root:
                dockerfile += "USER paradrop\n"
        elif as_root:
            # No packages to install but run as root.
            dockerfile += "USER root\n"

        dockerfile += "CMD {}\n".format(cmd_string)

        return dockerfile

    def isValid(self):
        """
        Check if configuration is valid.

        Returns a tuple (True/False, None or str).
        """
        # Check required fields.
        for field in Dockerfile.requiredFields:
            if getattr(self.service, field, None) is None:
                return (False, "Missing required field {}".format(field))

        command = self.service.command
        if not isinstance(command, basestring) and not isinstance(command, list):
            return (False, "Command must be either a string or list of strings")

        packages = self.service.build.get("packages", [])
        if not isinstance(packages, list):
            return (False, "Packages must be specified as a list")
        for pkg in packages:
            if re.search(r"\s", pkg):
                return (False, "Package name ({}) contains whitespace".format(pkg))

        return (True, None)

    def writeFile(self, path):
        """
        Generate Dockerfile and write to a file.
        """
        data = self.getString()
        with open(path, "w") as output:
            output.write(data)
