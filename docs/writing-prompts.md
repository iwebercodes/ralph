# Writing Effective Prompts

Your PROMPT.md file determines how well Ralph works. This page shows you how to write prompts that get reliable results.

## The Template

When you run `ralph init`, you get a template with these sections:

```markdown
# Goal

What you want to accomplish (1-2 sentences).

# Success Criteria

- [ ] First requirement
- [ ] Second requirement
- [ ] Third requirement

# Context (optional)

Background info Claude needs to know.

# Constraints (optional)

Rules or limitations to follow.
```

Each section serves a purpose.

## Writing the Goal

Your goal should be clear and specific. One task, not multiple.

**Too vague:**
```markdown
# Goal
Make the app better.
```

**Too broad:**
```markdown
# Goal
Add user authentication, a dashboard, and email notifications.
```

**Good:**
```markdown
# Goal
Add JWT-based user authentication with login and registration endpoints.
```

One sentence. One outcome. If you need multiple features, run Ralph multiple times.

## Writing Success Criteria

Success criteria are checkboxes that define "done". Ralph uses these to know when the task is complete.

**Testable criteria** - Can someone verify this yes/no?
```markdown
- [ ] GET /users returns a list of users
- [ ] Each user object has id, name, and email fields
- [ ] Response includes pagination metadata
```

**Vague criteria** - What does this mean?
```markdown
- [ ] API works well
- [ ] Code is clean
- [ ] Tests pass
```

Good criteria are:
- Specific (what exactly should happen)
- Testable (you can verify they're met)
- Complete (nothing left ambiguous)

## Common Mistakes

### 1. Too many goals at once

```markdown
# Goal
Add user auth, fix the cart bug, and improve performance.
```

Split this into three separate Ralph runs.

### 2. Missing success criteria

```markdown
# Goal
Refactor the database layer.
```

Without criteria, Claude doesn't know when to stop. Add:
```markdown
# Success Criteria
- [ ] Database logic is in src/db/ directory
- [ ] Each model has its own file
- [ ] No raw SQL in route handlers
- [ ] Existing tests still pass
```

### 3. Vague success criteria

```markdown
- [ ] Code follows best practices
- [ ] Error handling is improved
```

Be specific:
```markdown
- [ ] All async functions have try/catch blocks
- [ ] Errors return appropriate HTTP status codes
- [ ] Error responses include message and code fields
```

### 4. No context for a complex codebase

If your project has non-obvious structure, add context:
```markdown
# Context

This is a Next.js app with:
- Pages in src/pages/
- API routes in src/pages/api/
- Database models in prisma/schema.prisma
- Tests in __tests__/
```

## Example: Before and After

**Before (will struggle):**
```markdown
# Goal
Add a contact form to the website.
```

**After (will succeed):**
```markdown
# Goal
Add a contact form to the marketing site that sends emails.

# Success Criteria
- [ ] Form at /contact with name, email, message fields
- [ ] Email validation before submission
- [ ] Form sends to contact@example.com via SendGrid
- [ ] Success message appears after submission
- [ ] Form has loading state while sending
- [ ] Error message appears if send fails

# Context
- This is a Next.js site
- SendGrid is already configured in lib/email.ts
- Design should match existing forms in src/components/forms/

# Constraints
- Use existing form styles, don't create new CSS
- No new dependencies
```

## Using Constraints

Constraints help prevent over-engineering and scope creep:

```markdown
# Constraints
- Don't modify existing tests
- Keep changes under 200 lines
- No new dependencies
- Don't refactor unrelated code
```

## Next Steps

- [See examples](./examples/index.md) - Real PROMPT.md files for common tasks
- [Get started](./getting-started.md) - Install and run Ralph
- [Troubleshooting](./troubleshooting/index.md) - When things don't work
