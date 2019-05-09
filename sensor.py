import logging

import datetime
import xml.etree.ElementTree as ET
import xml.dom.minidom
from datetime import timedelta, datetime
from tzlocal import get_localzone

import random
import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION


_LOGGER = logging.getLogger(__name__)

ATTR_STOP_ID = 'Stop ID'
ATTR_TYPE = 'Type'
ATTR_ROUTE = 'Route'
ATTR_DUE_IN = 'Due in'
ATTR_DUE_AT = 'Due at'
ATTR_STOP_ID = 'Stop ID'
ATTR_NEXT_UP = 'Later Bus'

ATTRIBUTION = "Data provided by Verbund Linie"

DEFAULT_NAME = 'Next Bus'
ICON_BUS = 'mdi:bus'
ICON_TRAIN = 'mdi:train'

SCAN_INTERVAL = timedelta(minutes=1)
TIME_STR_FORMAT = '%H:%M'

CONF_API_ENDPOINT = 'api_endpoint'
CONF_STOP_ID = 'stopid'
CONF_LINE = 'line'
CONF_MAX_RESULTS = 'max_results'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_ENDPOINT): cv.string,
    vol.Required(CONF_STOP_ID): cv.string,
    vol.Optional(CONF_LINE, default=""): cv.string,
    vol.Optional(CONF_MAX_RESULTS, default=10): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


headers = {'Content-Type': 'text/xml'}
data = '''<Trias xmlns="http://www.vdv.de/trias" xmlns:siri="http://www.siri.org.uk/siri" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.2">
    <ServiceRequest>
        <siri:RequestTimestamp>{{timestampHeader}}</siri:RequestTimestamp>
        <siri:RequestorRef>mdv</siri:RequestorRef>
        <RequestPayload>
            <StopEventRequest>
                <Location>
                    <LocationRef>
                        <StopPointRef>{{stopid}}</StopPointRef>
                    </LocationRef>
                </Location>
                <Params>
                    <NumberOfResults>{{max_results}}</NumberOfResults>
                    <StopEventType>departure</StopEventType>
                </Params>
            </StopEventRequest>
        </RequestPayload>
    </ServiceRequest>
</Trias>'''

def due_in_minutes(timestamp):
    """Get the time in minutes from a timestamp.
    The timestamp should be in the format day/month/year hour/minute/second
    """
    diff = timestamp - dt_util.now()
    return str(int(diff.total_seconds() / 60))

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the sensor platform."""
    stop = config.get(CONF_STOP_ID)
    name = config.get(CONF_NAME)
    api_endpoint = config.get(CONF_API_ENDPOINT)
    line = config.get(CONF_LINE)
    max_results = config.get(CONF_MAX_RESULTS)
    data = TransportData(api_endpoint, stop, line, max_results)
    add_entities([VerbundLinieTransportSensor(data, stop, line, name)], True)

class VerbundLinieTransportSensor(Entity):
    """Implementation of an Verbind Linie public transport sensor."""

    def __init__(self, data, stop, line, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stop = stop
        self._line = line
        self._times = self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._times is not None:
            next_up = "None"
            if len(self._times) > 1:
                next_up = self._times[1][ATTR_ROUTE] + " in "
                next_up += self._times[1][ATTR_DUE_IN]

            return {
                ATTR_DUE_IN: self._times[0][ATTR_DUE_IN],
                ATTR_DUE_AT: self._times[0][ATTR_DUE_AT],
                ATTR_STOP_ID: self._times[0][ATTR_STOP_ID],
                ATTR_ROUTE: self._times[0][ATTR_ROUTE],
                ATTR_TYPE: self._times[0][ATTR_TYPE],
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_NEXT_UP: next_up
            }

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return 'min'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        _LOGGER.debug('next transport is a ' + self._times[0][ATTR_TYPE])
        if self._times is not None and self._times[0][ATTR_TYPE].lower().__contains__('bus'):
        # if bool(random.getrandbits(1)):
            _LOGGER.debug('bus')
            return ICON_BUS
        else:
            _LOGGER.debug('tram')
            return ICON_TRAIN

    def update(self):
        """Get the latest data from opendata.ch and update the states."""
        self.data.update()
        self._times = self.data.info
        try:
            self._state = self._times[0][ATTR_DUE_IN]
        except TypeError:
            pass

class TransportData:
    """Pull data from the api."""

    def __init__(self, api_endpoint, stop, route, max_results):
        """Initialize the data object."""
        self.stop = stop
        self.line = route
        self._max_results = max_results
        self._RESOURCE = api_endpoint
        self.info = [{ATTR_DUE_AT: 'n/a',
                      ATTR_ROUTE: self.line,
                      ATTR_DUE_IN: 'n/a'}]

    def update(self):
        """Get the latest data from the api"""
        _LOGGER.debug("@update")
        self.info = []
        connections = self.fetchConnections()
        _LOGGER.debug("found " + str(len(connections)) + ' connections for stop ' + self.stop)

        if self.line:
            _LOGGER.debug("showing only line " + self.line)
        else:
            _LOGGER.debug("showing all lines")

        for connection in connections:
            due_at = connection.get('departure')
            line = connection.get('line')
            origin = connection.get('origin')
            destination = connection.get('destination')
            stopid = connection.get('stopid')
            transport_type = connection.get('type')
            if not self.line or self.line.lower() == line.lower():
                _LOGGER.debug("line " + line + " matches")
                data = {ATTR_DUE_AT: due_at.isoformat(),
                            ATTR_ROUTE: line,
                            ATTR_TYPE: transport_type,
                            ATTR_STOP_ID: stopid,
                            ATTR_DUE_IN: due_in_minutes(due_at)}
                self.info.append(data)

        if not self.info:
            self.info = [{ATTR_DUE_AT: 'n/a',
                          ATTR_ROUTE: self.line,
                          ATTR_DUE_IN: 'n/a'}]

    def fetchConnections(self):
        utc_now = datetime.utcnow().isoformat()
        request_data = data.replace('{{stopid}}', self.stop)
        request_data = request_data.replace('{{timestampHeader}}', utc_now + 'Z')
        request_data = request_data.replace('{{max_results}}', str(self._max_results))
        response = requests.post(self._RESOURCE, data=request_data, headers=headers)
        return self.parseConnections(response.content)

    def parseConnections(self, xmlstring):
        self.connections = list()
        xmldoc = xml.dom.minidom.parseString(xmlstring)
        stopevents = xmldoc.getElementsByTagName("StopEventResult")
        for stopevent in stopevents:
            stopid = stopevent.getElementsByTagName("StopPointRef")[0].firstChild.nodeValue
            service = stopevent.getElementsByTagName("Service")[0]
            line = service.getElementsByTagName("PublishedLineName")[0].getElementsByTagName("Text")[0].firstChild.nodeValue
            origin = service.getElementsByTagName("OriginText")[0].getElementsByTagName("Text")[0].firstChild.nodeValue
            destination = service.getElementsByTagName("DestinationText")[0].getElementsByTagName("Text")[0].firstChild.nodeValue
            transport_type = service.getElementsByTagName("Mode")[0].getElementsByTagName("Name")[0].getElementsByTagName("Text")[0].firstChild.nodeValue

            timestring = stopevent.getElementsByTagName("TimetabledTime")[0].firstChild.nodeValue
            now = datetime.now().astimezone(get_localzone())
            departuretime = datetime.strptime(timestring, "%Y-%m-%dT%H:%M:%S%z").astimezone(get_localzone())
            delta = departuretime - now

            data = {
                'line': line,
                'origin': origin,
                'destination': destination,
                'departure': departuretime,
                'delta': delta,
                'type': transport_type,
                'stopid': stopid,
            }
            self.connections.append(data)
        return self.connections