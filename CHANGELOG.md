# Changelog

This is a changelog that should include all notable changes for the RPG Player
Project.

## Unreleased

### Added

- Added missing `pytest-cov` dev dependency
- Added a fallback to the token counter code for `gpt-6` since it is not yet in
  the open source library
- Added extra logging around speech so you can more easily figure out issues
- Added a timeout to response and speaking, this is a stop-gap measure to
  prevent the UI from locking. Previously this meant you'd need to close and
  reopen it

### Changed

- Improved OpenAI voice actor class to speak faster and report errors nicely
- Altered instances of OpenAI's `gpt-5.6` to `gpt-6` as it is currently the
  better and cheaper model
- Updated dependencies

### Removed

- Removed Elevenlabs tag transformer. It's better to do this in the system
  prompt of the agents.
- Removed old `requirements.txt` file

## Version 0.2.0

### Added

- Added `CHANGELOG.md`
- Added `TODO.md`
- Added an LLM agent skill: `.agents/skills/unit-test/`
- Added more tests for various parts that were refactored
- Added checks for recording of blank or empty audio

### Changed

- Altered how transcription API works, it now returns some domain objects
- Refactored a lot of code to be type safe for `basedpyright`
- Refactored code to use non-deprecated types
- Moved code around and split it up into domain objects in some files and
  implementations in others
- Moved to using `Protocol` for many domain objects rather than `ABC`
- Updated `AGENTS.md` to be hand written
- Fixed some minor bugs in configuration
- Made configuration use typed dictionaries in some places
- Replaced `pre-commit` with `prek`
- Tidied up `README.md`
- Updated libraries in `uv.lock`

### Removed

- Removed extra keyword arguments parsing from Agents
- Remove `flake8`, we can rely on `ruff`, `black` and `basedpyright`

## Version 0.1.0

- Initial version of the project
- Contained `textual` implementation of the RPG Player Project
- Uses multiple libraries like `openai`, `ollama`, etc.
