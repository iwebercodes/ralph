# Example: Adding a Feature

This example shows how to add a contact form feature to a Next.js website.

## The Task

Add a contact form that:
- Collects name, email, and message
- Validates input
- Sends email via SendGrid
- Shows success/error feedback

## The PROMPT.md

```markdown
# Goal

Add a contact form to the marketing site that sends emails via SendGrid.

# Success Criteria

- [ ] Form at /contact with name, email, message fields
- [ ] Name is required, minimum 2 characters
- [ ] Email validates format before submission
- [ ] Message is required, minimum 10 characters
- [ ] Submit button shows loading state while sending
- [ ] Success message appears after successful send
- [ ] Error message appears if send fails
- [ ] Form clears after successful submission
- [ ] Email sent to contact@example.com via SendGrid API

# Context

This is a Next.js 14 app with:
- App router (pages in src/app/)
- Tailwind CSS for styling
- SendGrid API key in SENDGRID_API_KEY environment variable
- Existing form components in src/components/forms/

# Constraints

- Use existing form styles from src/components/forms/Input.tsx
- Don't install new dependencies (SendGrid SDK already installed)
- Keep the contact page under 200 lines
- Don't modify other pages
```

## Why This Works

**Specific goal:** One feature, clearly described.

**Testable criteria:** Each checkbox can be verified yes/no:
- "Form at /contact" - visit the URL, see the form
- "Name is required, minimum 2 characters" - try submitting with 1 character
- "Success message appears" - submit valid form, see message

**Useful context:** Claude knows the tech stack and where things are:
- "App router (pages in src/app/)" - where to create the page
- "Existing form components" - what to reuse
- "SendGrid API key in..." - how to access credentials

**Focused constraints:** Prevent scope creep:
- "Use existing form styles" - don't redesign
- "Don't install new dependencies" - use what's there
- "Keep under 200 lines" - stay focused

## Running It

```bash
ralph init
# Paste the PROMPT.md above
ralph run
```

Expected output:
```
[1/20] Working...
  Signal: CONTINUE
  Files changed: 3

[2/20] Working...
  Signal: CONTINUE
  Files changed: 2

[3/20] Working...
  Signal: DONE
  Files changed: 0 (1/3 verification)

...

Goal achieved in 5 rotations (3m 42s)
```

## Adapting This Example

For your own feature:

1. **Change the goal** to your feature
2. **List specific criteria** - what does "done" look like?
3. **Add your context** - tech stack, file locations, conventions
4. **Set boundaries** - what should NOT change?

## Related

- [Writing prompts](../writing-prompts.md) - More on effective prompts
- [Fix a bug example](./fix-bug.md) - Different task type
- [Refactor example](./refactor.md) - Code restructuring
