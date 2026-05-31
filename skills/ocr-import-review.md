# Skill: OCR Import Review

Use this skill when implementing OCR upload, extraction, or review workflows.

## Core Rule

OCR output must never auto-publish.

## Required Workflow

Upload -> OCR -> AI extraction -> Review Queue -> Admin approval -> Publish

## Required Metadata

- source_file_id
- page number
- OCR confidence
- extraction confidence
- reviewer
- review timestamp

## Admin Review UI

Show source preview, OCR text, extracted structured question, editable fields, and approval controls.
