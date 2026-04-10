# Onboarding Guide

## Goal

Bring a new tenant to a usable control-plane state without bypassing backend governance.

## Steps

1. Create Organization
   Enter the group name, base country, and reporting currencies.

2. Create Entity
   Add the first operating entity with reporting framework and fiscal-year settings.

3. Select Modules
   Enable the modules the team needs first. These toggles call the backend module registry.

4. Upload Initial Data
   Upload the starting chart of accounts through the existing upload path and review airlock results.

5. Completion
   Review the current backend truth and continue into the control plane.

## Operator Notes

- Empty states explain what to create next.
- Loading states indicate backend fetches in progress.
- Error states explain what failed and what to try next.
- The onboarding wizard does not simulate setup state locally.
