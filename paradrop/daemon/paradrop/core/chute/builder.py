"""
The Chute Builder interprets the chute specification, which comes from a
paradrop.yaml file or from a JSON object via a cloud update. The Chute
Builder then produces a valid Chute ojbect with one or more Service
objects.

There are different versions of the chute specification in code
repositories, and so the intent is to encapsulate this complexity within
the ChuteBuilder implementation. Other code modules, especially the
execution plan pipeline, should be able to rely on a relatively stable
Chute and Service object interface.

+----------------------------+                   +---------------+
|                            |         interpret |               |
| Chute Specification        | <-----------------+ Chute Builder |
| serialized as YAML or JSON |                   |               |
| in a variety of formats    |                   ++-------------++
|                            |                    |             |
+----------------------------+                    |  construct  |
                                                  |             |
                                                  v             |
                                                                |
+----------------+                         +-------+            |
|                |                         |       |            |
| Execution Plan |                         | Chute |            v
| -------------- +-----------------------> |       | has 1+
| function 1     |                         +-------o---+---------+
| ...            | consume                             |         |
| function N     |                                     | Service |
|                +-----------------------------------> |         |
+----------------+                                     +---------+
"""


from .chute import Chute
from .service import Service


class ChuteBuilder(object):
    """
    Build a composite chute object from a chute specification.

    Implementations of ChuteBuilder are responsible for interpreting
    the chute specification, which comes from a paradrop.yaml file or
    JSON object via cloud update. The ChuteBuilder then produces a valid
    Chute object with one or more Service objects.
    """
    def configure_chute(self, config):
        for field in ["name", "version", "description"]:
            value = config.get(field, "unknown")
            setattr(self.chute, field, value)

    def create_chute(self, config):
        return NotImplemented

    def create_services(self, config):
        return NotImplemented

    def get_chute(self):
        return self.chute


class SingleServiceChuteBuilder(ChuteBuilder):
    """
    Build a pre-0.12 single-service chute.

    ** Example configuration**:

    .. sourcecode:: yaml

       name: seccam
       description: A Paradrop chute that performs motion detection using a simple WiFi camera.
       version: 1

       net:
         wifi:
           type: wifi
           intfName: wlan0
           dhcp:
             start: 4
             limit: 250
             lease: 12h
           ssid: seccam42
           key: paradropseccam
           options:
             isolate: true
             maxassoc: 100
       web:
         port: 5000
    """

    # Fields that should be present in updates but not chute objects.
    UpdateSpecificArgs = ['deferred']

    def create_chute(self, config):
        self.chute = Chute(config, strip=self.UpdateSpecificArgs)

    def create_services(self, config):
        service = Service(self.chute, None)

        service.command = config.get("command", None)
        service.image = config.get("use", None)
        service.source = "."
        service.type = config.get("type", "normal")

        service.environment = config.get("environment", {})

        self.chute.services = [service]


class MultiServiceChuteBuilder(ChuteBuilder):
    """
    Build a modern multi-service chute.

    ** Example configuration**:

    .. sourcecode:: yaml

       name: seccam
       description: A Paradrop chute that performs motion detection using a simple WiFi camera.
       version: 1

       services:
         main:
           type: light
           source: .
           image: python2
           command: python -u seccam.py

           environment:
             IMAGE_INTERVAL: 2.0
             MOTION_THRESHOLD: 40.0
             SECCAM_MODE: detect

           interfaces:
             wlan0:
               type: wifi-ap

               dhcp:
                 leasetime: 12h
                 limit: 250
                 start: 4

               wireless:
                 ssid: seccam42
                 key: paradropseccam
                 hidden: false
                 isolate: true

               requirements:
                 hwmode: 11g

           requests:
             as-root: true
             port-bindings:
               - external: 81
                 internal: 81

         db:
           type: image
           image: mongo:3.0

       web:
         service: main
         port: 5000
    """
    def create_chute(self, config):
        self.chute = Chute({})

        for field in ["name", "version", "description"]:
            value = config.get(field, "unknown")
            setattr(self.chute, field, value)

        self.chute.config = config.get("config", {})

    def create_services(self, config):
        services = []

        for name, spec in config.get("services", {}).iteritems():
            service = Service(self.chute, name)

            service.command = spec.get("command", None)
            service.image = spec.get("image", None)
            service.source = spec.get("source", ".")
            service.type = spec.get("type", "normal")

            service.environment = spec.get("environment", {})

            services.append(service)

        self.chute.services = services


def build_chute(config):
    if 'services' in config:
        builder = MultiServiceChuteBuilder()
    else:
        builder = SingleServiceChuteBuilder()

    builder.create_chute(config)
    builder.create_services(config)

    return builder.get_chute()
