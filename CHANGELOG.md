# Changelog

## Next version

### 🚀 New

* Added `Trigger` class.

### ✨ Improved

* Allow passing subject and other parameters to `send_critical_error_email`.


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
