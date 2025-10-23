# Changelog

## 0.5.21 - October 22, 2025

### 🔧 Fixed

* Fix typing in `pubsub.py` iterator overloads.


## 0.5.20 - October 6, 2025

### 🚀 New

* Added `timeout` decorator to set a timeout on async functions.

### ✨ Improved

* Allow to remove the preface in critical error emails that indicates that the email is a critical error notification.


## 0.5.19 - August 10, 2025

### ✨ Improved

* Support power cycling AG cameras that are connected to a NPS outlet. The configuration for AG cameras has changed significantly and the new section `devices.agcams` now includes the type of connection (`nps` or `poe`) with the actor/outlet information in the case of `nps` and the port interface in the case of `poe`.


## 0.5.18 - August 9, 2025

### 🔧 Fixed

* Fix check of new status in `LVMActor`.


## 0.5.17 - August 8, 2025

### ✨ Improved

* `read_nps()` now supports passing a list of NPS to read and is more flexible about the format of the input actors.

### 🔧 Fixed

* Improve handling of empty wind data in the LCO weather API.


## 0.5.16 - June 13, 2025

### 🔧 Fixed

* New weather API now returns wind speeds in miles per hour.
* Fix deprecation in `polars.dt.datetime()`.
* Convert temperature from Fahrenheit to Celsius after LCO API change.
* Handle empty data in the LCO weather API.
* Pin `pymodbus==3.9.1`.
* Pin `click<8.2.0`.


## 0.5.15 - June 9, 2025

### 🔧 Fixed

* Updated the LCO weather API endpoint.


## 0.5.14 - April 16, 2025

### 🔧 Fixed

* Fixed optional import of `netmiko` in `lvmopstools.devices.switch`.
* Default to UTC if the `datetime` passed to `is_weather_data_safe` does not include a time zone.


## 0.5.13 - April 15, 2025

### 🔧 Fixed

* Correctly filter data between initial and end dates in `get_from_lco_api`.


## 0.5.12 - April 15, 2025

### ✨ Improved

* `get_weather_data`: Iterate over the time interval in small increments to ensure that the LCO weather API returns all the data.
* `is_weather_data_safe`: Added argument `now` to define the reference point from which to determine if the weather is safe.


## 0.5.11 - March 21, 2025

### ✨ Improved

* [#14](https://github.com/sdss/lvmopstools/pull/14) Add `get_poe_port_info()`.
* Move `power_cycle_ag_camera` to `lvmopstools.devices.switch`.


## 0.5.10 - March 10, 2025

### ✨ Improved

* [#13](https://github.com/sdss/lvmopstools/pull/13) Allow to toggle an ion pump connected to an NPS outlet.
* Use system ping in `is_host_up` if the process is not running as root.
* Round up pressure and differential voltage.


## 0.5.9 - February 24, 2025

### 🚀 New

* Added `power_cycle_ag_camera` utility function.


## 0.5.8 - February 24, 2025

### 🚀 New

* Added `is_host_up` utility function.


## 0.5.7 - January 13, 2025

### ✨ Improved

* Return the differential voltage in `read_ion_pumps`.
* Updated IP addresses for ion pumps.
* `Retrier` now accepts a `timeout` parameter.


## 0.5.6 - January 11, 2025

### 🔧 Fixed

* Fix the signal registers to read ion pump voltages.
* Do not stop event loop in `LVMActor` when restarting in mode `exit`.

### ⚙️ Engineering

* Improved typing of `with_timeout` function.


## 0.5.5 - December 27, 2024

### 🔧 Fixed

* Install `influxdb-client` with the `async` extra.


## 0.5.4 - December 27, 2024

This release has been pulled.


## 0.5.3 - December 27, 2024

### 🔧 Fixed

* Import `TypedDict` from `typing_extensions` instead of `typing` to avoid issues with Pydantic in <3.12.


## 0.5.2 - December 23, 2024

### ✨ Improved

* Add footnote to the critical email template.

### 🔧 Fixed

* Fix extras dependencies and add an `all` extra with all the extra dependencies except `pyds9`.


## 0.5.1 - December 22, 2024

### 💥 Breaking changes

* Moved `lvmopstools.slack` dependencies to `slack` extra.
* Renamed `schedule` extra to `ephemeris`.

### 🚀 New

* Added `Trigger` class.

### ✨ Improved

* Added a more general `send_email` function.
* Allow passing subject and other parameters to `send_critical_error_email`.

### ⚙️ Engineering

* Updated management of dev dependencies.
* Add sections `tool.hatch.build.targets.sdist` and `tool.hatch.build.wheel` to `pyproject.toml`.


## 0.5.0 - December 21, 2024

### 💥 Breaking changes

* Renamed `schedule` to `ephemeris`.

### 🚀 New

* [#10](https://vscode.dev/github/sdss/lvmopstools/pull/10) Added a `pubsub` module with tools to emit and subscribe to events using RabbitMQ.
* [#11](https://vscode.dev/github/sdss/lvmopstools/pull/11) Added a `slack` module with tools to send messages to Slack.
* [#12](https://vscode.dev/github/sdss/lvmopstools/pull/12) Added a `notifications` module.
* Added `ephemeris.is_sun_up`.


## 0.4.4 - December 5, 2024

### ✨ Improved

* Allow passing kwargs to the `AMQPClient` in `CluClient`.


## 0.4.3 - November 29, 2024

### 🚀 New

* Add `with_timeout()` to utils.

### ✨ Improved

* Add test coverage for `utils.py`.


## 0.4.2 - November 27, 2024

### ✨ Improved

* Add option to `Retrier` to immediately raise an exception if the exception class matches a given list of exceptions.


## 0.4.1 - November 27, 2024

### 🚀 New

* Added schedule tools, migrated from `lvmapi`.


## 0.4.0 - November 27, 2024

### 💥 Breaking changes

* Removed the option `raise_on_max_attempts` from `Retrier`. If the number of attempts is reached, the retrier will always raise an exception.

### 🚀 New

* Add `get_weather_data` and `is_weather_data_safe` functions to retrieve weather data from the LCO API (ported from `lvmapi`).
* Added `Kubernetes` class and InfluxDB tools.

### ✨ Improved

* Better typing for `Retrier.__call__()`.
* `Retrier` now accepts `on_retry` which is called when before retry is attempted with the exception that caused the retry.

### 🔧 Fixed

* Fix some unittests.


## 0.3.9 - September 17, 2024

### 🔧 Fixed

* Make sure we close the connection to the thermistors.


## 0.3.8 - September 16, 2024

### 🚀 New

* Added `channel_to_valve` mapping function to `lvmopstools.devices.ion`.

### ✨ Improved

* Re-export all public device functions in `lvmopstools.devices`.
* Updated thermistor configuration.


## 0.3.7 - September 15, 2024

### ✨ Improved

* Report `None` for ion pump pressure if the value is less that 1e-8.


## 0.3.6 - September 15, 2024

### ⚙️ Internal

* Removed unnecessary `astropy` dependency.


## 0.3.5 - September 13, 2024

### 🔧 Fixed

* Fixed typo in `spectrograph_status` function name.


## 0.3.4 - September 12, 2024

### ⚙️ Internal

* Improved typing.


## 0.3.3 - September 12, 2024

### 🚀 New

* Added `lvmopstools.devices.nps.read_nps`.

### ✨ Improved

* Several functions in `lvmopstools.devices.specs` now accept `ignore_errors` which replaces the values of unreachable devices with `None`.
* By default, return all values for all spectrographs in `spectrograph_pressures` and `spectrograph_mechanics`.
* Return `None` if ion pump fails to read.
* Allow to pass `internal` to `send_clu_command`.

### 🔧 Fixed

* `Retrier` backoff delay is now calculated as `delay * exponential_backoff_base ** (attempt - 1)`.


## 0.3.2 - September 12, 2024

### ⚙️ Internal

* Test `taiki-e/create-gh-release-action` workflow to release a new version.


## 0.3.1 - September 12, 2024

### 🚀 New

* Moved additional spectrograph functions to `lvmopstools.devices.specs`.


## 0.3.0 - September 12, 2024

### 🚀 New

* Added support for reading spectrograph status, ion pumps, and thermistors.
* Added `CliClient` class.

### ⚙️ Internal

* Format code using `ruff`.
* Migrate package management to `uv`.


## 0.2.0 - March 25, 2024

### 🚀 New

* Added `LVMActor` class with actor state, restart, and troubleshooting framework.


## 0.1.0 - January 19, 2024

### 🚀 New

* Initial version with `Retrier`, `AsyncSocketHandler`, and DS9 utilities.
