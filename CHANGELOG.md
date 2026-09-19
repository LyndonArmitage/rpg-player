# Changelog

This is a changelog that should include all notable changes for the RPG Player
Project.

## Unreleased

### Added

### Changed

### Removed

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
- Tidied up README.md

### Removed

- Removed extra keyword arguments parsing from Agents

## Version 0.1.0

- Initial version of the project
- Contained `textual` implementation of the RPG Player Project
- Uses multiple libraries like `openai`, `ollama`, etc.
