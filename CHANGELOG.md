# Changelog

## Next version

### 🚀 New

* Added `lvmopstools.devices.nps.read_nps`.

### ✨ Improved

* Several functions in `lvmopstools.devices.specs` now accept `ignore_errors` which replaces the values of unreachable devices with `None`.
* By default, return all values for all spectrographs in `spectrograph_pressures` and `spectrograph_mechanics`.
* Return `None` if ion pump fails to read.
* Allow to pass `internal` to `send_clu_command`.

### 🐛 Fixed

* `Retrier` backoff delay is now calculated as `delay * exponential_backoff_base ** (attempt - 1)`.


## 0.3.2 - September 12, 2024

### ⚙️ Engineering

* Test `taiki-e/create-gh-release-action` workflow to release a new version.


## 0.3.1 - September 12, 2024

### 🚀 New

* Moved additional spectrograph functions to `lvmopstools.devices.specs`.


## 0.3.0 - September 12, 2024

### 🚀 New

* Added support for reading spectrograph status, ion pumps, and thermistors.
* Added `CliClient` class.

### ⚙️ Engineering

* Format code using `ruff`.
* Migrate package management to `uv`.


## 0.2.0 - March 25, 2024

### 🚀 New

* Added `LVMActor` class with actor state, restart, and troubleshooting framework.


## 0.1.0 - January 19, 2024

### 🚀 New

* Initial version with `Retrier`, `AsyncSocketHandler`, and DS9 utilities.
