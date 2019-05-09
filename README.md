# HomeAssistant Verbund Linie component

This is a sensor component for HomeAssistant.

### Installation

Copy this folder to `<config_dir>/custom_components/verbund_linie/`.

Add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sensor:
  sensor:
  - platform: verbund_linie
    name: Krenngasse
    stopid: 'at:46:3171'
    # Optional field, if set only this line will be shown
    line: 3
    # Optional field, maximum stop event that will be fetched, default is 10
    max_results: 3
    # this url of the api endpoint
    # The url is not public and the license does the redistribution of the url, but you can request access for free. See the FAQ at https://www.verbundlinie.at/fahrplan/rund-um-den-fahrplan/link-zum-fahrplan# (only in german)
    api_endpoint: api_enpoint_url
```