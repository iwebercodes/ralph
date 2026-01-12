# Ralph Technology Specification

## Executive Summary

This document evaluates technology options for reimplementing Ralph, addressing the issues identified in ANALYSIS.md while preparing for future growth (more subcommands, plugins, multiple agent types).

**Recommendation: Python with Typer**

Python offers the best balance of:
- Ubiquitous runtime (pre-installed on macOS/Linux, easy Windows install)
- Excellent CLI frameworks (Typer/Click)
- Strong testing ecosystem (pytest)
- Low barrier to contribution
- Optional single-binary distribution via PyInstaller

---

## Requirements Summary

From the goal specification:

| Requirement | Priority |
|-------------|----------|
| Single binary/file for users | High |
| Cross-platform (Linux, macOS, Windows/WSL) | High |
| Minimal runtime dependencies | High |
| Subcommand structure (`ralph init`, `ralph run`, etc.) | High |
| Clean argument parsing with help system | High |
| `.ralph/` folder for state, `.ralphignore` support | High |
| Claude Code skills integration | High |
| Type checking and linting | Medium |
| Unit and integration tests | High |
| CI/CD with cross-platform matrix | High |

---

## Technology Evaluation

### 1. Bash (Keep Current)

**What it is:** The current implementation - a ~460 line bash script.

**Distribution:**
- Copy `ralph.sh` to project or PATH
- No build step required
- Single file, but not a "binary"

**Cross-Platform:**
- ❌ **macOS broken**: Uses `md5sum` (GNU coreutils), macOS has `md5 -r`
- ❌ Windows requires WSL or Git Bash
- ⚠️ Bash version differences (3.x on macOS vs 5.x on Linux)

**CLI Design:**
- Manual argument parsing with `case` statements
- No framework for subcommands - would need to implement from scratch
- Help text is manual string construction

**Testing:**
- [shunit2](https://github.com/kward/shunit2) - xUnit-style testing for shell
- Testing bash is awkward compared to other languages
- No type checking possible

**Development Experience:**
- No IDE support, no autocompletion
- Error messages are cryptic
- Debugging is difficult

**Claude Code Skills:**
- ✅ Works - just a script to run

**Verdict:** ❌ Not recommended. The current issues stem from bash's limitations. Adding subcommands, proper error handling, and cross-platform support would require significant effort with diminishing returns.

---

### 2. POSIX sh

**What it is:** Portable shell that works everywhere, but even more limited than bash.

**Distribution:**
- Same as bash - single script file

**Cross-Platform:**
- ✅ Truly portable across Unix systems
- ❌ Still requires WSL on Windows
- ❌ Loses bash conveniences like `[[`, arrays, `echo -e`

**CLI Design:**
- Even more manual than bash
- No modern CLI framework exists

**Testing:**
- shunit2 supports POSIX sh
- Same awkwardness as bash

**Development Experience:**
- Worse than bash - more restricted syntax
- Harder to write maintainable code

**Claude Code Skills:**
- ✅ Works

**Verdict:** ❌ Not recommended. Going backwards in capability. Ralph needs to grow, not shrink.

---

### 3. Python with Typer

**What it is:** Python CLI framework built on Click, using type hints for argument parsing.

**Distribution:**
- **Option A**: `pip install ralph-loop` (requires Python)
- **Option B**: [PyInstaller](https://pyinstaller.org/) for standalone executables
- Python 3.8+ is pre-installed on macOS and most Linux distros
- Windows: Python from Microsoft Store or official installer

**Cross-Platform:**
- ✅ Full support for Linux, macOS, Windows (native, not just WSL)
- ✅ No platform-specific code needed for file operations
- ✅ `hashlib.md5()` works everywhere (solves the md5sum issue)

**CLI Design:**
- [Typer](https://typer.tiangolo.com/) provides:
  - Subcommands via decorated functions
  - Automatic `--help` generation
  - Type-based argument validation
  - Shell completion (bash, zsh, fish, PowerShell)
  - Rich error messages with colors

Example:
```python
import typer

app = typer.Typer()

@app.command()
def init():
    """Initialize Ralph in the current project."""
    ...

@app.command()
def run(test_cmd: str = None, max_iter: int = 20):
    """Run the Ralph loop."""
    ...

@app.command()
def status():
    """Show current Ralph state."""
    ...

if __name__ == "__main__":
    app()
```

**Testing:**
- [pytest](https://docs.pytest.org/) - industry standard
- Typer includes `CliRunner` for testing CLI invocations
- Easy mocking, fixtures, parametrization

**Development Experience:**
- Strong IDE support (VS Code, PyCharm)
- Type hints with mypy for static analysis
- Ruff for fast linting
- Large ecosystem of libraries

**Claude Code Skills:**
- ✅ Works - run `ralph` command or `python -m ralph`
- Can also be imported as a library for deeper integration

**Verdict:** ✅ **Recommended**. Best balance of accessibility, capability, and maintainability.

---

### 4. Deno

**What it is:** TypeScript/JavaScript runtime with built-in tooling and `deno compile` for single binaries.

**Distribution:**
- [deno compile](https://docs.deno.com/runtime/reference/cli/compile/) creates standalone executables
- Cross-compilation supported (build Linux binary on macOS, etc.)
- Users don't need Deno installed to run compiled binary

**Cross-Platform:**
- ✅ Compiles to Linux, macOS, Windows natively
- ✅ Single binary ~50-100MB (includes runtime)

**CLI Design:**
- [Cliffy](https://cliffy.io/) - CLI framework for Deno
- Or use [std/cli](https://deno.land/std/cli) from standard library
- TypeScript provides type safety

**Testing:**
- Built-in test runner (`deno test`)
- Good coverage tooling

**Development Experience:**
- TypeScript with full type checking
- Built-in formatter, linter
- No node_modules, lockfile-based dependencies

**Claude Code Skills:**
- ✅ Works - compiled binary or `deno run`

**Concerns:**
- Deno is less common than Python - higher barrier to contribution
- Binary size is significant (~80MB)
- Ecosystem smaller than Node.js/Python

**Verdict:** ⚠️ Viable alternative. Good if team prefers TypeScript, but Python is more accessible.

---

### 5. Bun

**What it is:** Fast JavaScript/TypeScript runtime with `bun build --compile` for single binaries.

**Distribution:**
- [bun build --compile](https://bun.com/docs/bundler/executables) creates standalone executables
- Cross-compilation supported
- Binaries are ~50MB+

**Cross-Platform:**
- ✅ Linux, macOS, Windows
- ⚠️ Windows support is newer, less mature than Deno

**CLI Design:**
- Use existing Node.js CLI frameworks (Commander, Yargs)
- Or write custom parsing

**Testing:**
- Built-in test runner (`bun test`)
- Jest-compatible

**Development Experience:**
- TypeScript support
- Extremely fast
- npm-compatible

**Claude Code Skills:**
- ✅ Works

**Concerns:**
- Bun is very new (1.0 released late 2023)
- Less battle-tested than Deno or Python
- Smaller community

**Verdict:** ⚠️ Too new for a stable tool. Wait for more maturity.

---

### 6. Go with Cobra

**What it is:** Compiled language with excellent CLI support via Cobra framework.

**Distribution:**
- `go build` produces single static binary
- Binary size ~10-15MB
- No runtime dependencies
- Cross-compilation trivial: `GOOS=darwin GOARCH=amd64 go build`

**Cross-Platform:**
- ✅ Excellent support for Linux, macOS, Windows
- ✅ Native binaries, no emulation layer

**CLI Design:**
- [Cobra](https://cobra.dev/) is the industry standard:
  - Used by Kubernetes, Docker, GitHub CLI, Hugo
  - Subcommands, flags, arguments
  - Automatic help and shell completion
  - [Viper](https://github.com/spf13/viper) for config file support

**Testing:**
- Built-in `go test`
- Table-driven tests are idiomatic
- Good coverage tooling

**Development Experience:**
- Strong typing, fast compilation
- gofmt for formatting
- golangci-lint for linting
- Excellent concurrency support (goroutines)

**Claude Code Skills:**
- ✅ Works - just run the binary

**Concerns:**
- Higher learning curve than Python
- Fewer contributors may be able to help
- More verbose than Python for simple tasks

**Verdict:** ✅ Strong alternative. Best if you want smallest binaries and fastest runtime. Trade-off is accessibility.

---

### 7. Rust with Clap

**What it is:** Systems language with strong safety guarantees and the Clap CLI framework.

**Distribution:**
- `cargo build --release` produces single static binary
- Binary size ~5-10MB (smaller than Go)
- Cross-compilation via cross or cargo-zigbuild

**Cross-Platform:**
- ✅ Excellent support for Linux, macOS, Windows

**CLI Design:**
- [Clap](https://docs.rs/clap/) is the standard:
  - Derive macros for type-safe argument parsing
  - Subcommands, arguments, flags
  - Automatic help and shell completion

**Testing:**
- Built-in `cargo test`
- [assert_cmd](https://docs.rs/assert_cmd/) for CLI testing
- Strong testing culture in Rust community

**Development Experience:**
- Steepest learning curve
- Excellent tooling (rust-analyzer, clippy)
- Very fast resulting binaries
- Memory safety without GC

**Claude Code Skills:**
- ✅ Works

**Concerns:**
- Highest learning curve of all options
- Slower development velocity than Python
- Smallest potential contributor pool

**Verdict:** ⚠️ Overkill for Ralph. The safety and performance benefits don't outweigh the accessibility costs for a CLI tool of this nature.

---

## Comparison Matrix

| Criterion | Bash | POSIX sh | Python | Deno | Bun | Go | Rust |
|-----------|------|----------|--------|------|-----|-----|------|
| Single binary | ❌ | ❌ | ⚠️¹ | ✅ | ✅ | ✅ | ✅ |
| Cross-platform | ❌ | ⚠️ | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| Minimal deps | ✅ | ✅ | ⚠️² | ✅ | ✅ | ✅ | ✅ |
| CLI framework | ❌ | ❌ | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| Testing | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Contributor access | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ |
| Dev velocity | ⚠️ | ❌ | ✅ | ✅ | ✅ | ⚠️ | ❌ |
| Binary size | N/A | N/A | ~50MB | ~80MB | ~50MB | ~15MB | ~10MB |

¹ PyInstaller can create standalone executables
² Requires Python, but Python is ubiquitous

---

## Recommendation: Python with Typer

### Rationale

1. **Accessibility**: Python has the lowest barrier to entry. Most developers can read and contribute to Python code. This matters for an open-source tool.

2. **Ubiquity**: Python is pre-installed on macOS and most Linux distributions. Windows users can install it easily. No need to distribute binaries for most users.

3. **CLI Excellence**: Typer (built on Click) provides a best-in-class CLI experience with minimal code. Subcommands, help text, shell completion, and argument validation come free.

4. **Testing**: pytest is the gold standard for testing. Testing CLI applications in Python is straightforward.

5. **Optional Binary Distribution**: PyInstaller can create standalone executables for users who don't want to install Python. This gives us the best of both worlds.

6. **Claude Code Integration**: Works seamlessly as a command-line tool.

### Why Not Go?

Go would be my second choice. The single-binary story is cleaner, and Cobra is excellent. However:
- Fewer potential contributors
- More verbose for simple tasks
- Ralph doesn't need Go's concurrency or performance characteristics

If the project grows significantly and binary distribution becomes critical, migrating to Go remains an option.

---

## Implementation Plan

### CLI Framework

Use [Typer](https://typer.tiangolo.com/) v0.12+

```
pip install typer
```

### Project Structure

```
ralph/
├── pyproject.toml          # Project metadata, dependencies
├── README.md               # User-facing documentation
├── src/
│   └── ralph/
│       ├── __init__.py
│       ├── __main__.py     # Entry point: python -m ralph
│       ├── cli.py          # Typer app definition
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── init.py     # ralph init
│       │   ├── run.py      # ralph run
│       │   ├── status.py   # ralph status
│       │   ├── reset.py    # ralph reset
│       │   └── history.py  # ralph history
│       ├── core/
│       │   ├── __init__.py
│       │   ├── loop.py     # Main loop logic
│       │   ├── snapshot.py # File change detection
│       │   ├── prompt.py   # Prompt building
│       │   └── claude.py   # Claude CLI interaction
│       └── config/
│           ├── __init__.py
│           └── settings.py # Configuration handling
├── tests/
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_commands/
│   └── test_core/
└── .github/
    └── workflows/
        └── ci.yml          # GitHub Actions
```

### Dependencies

**Runtime:**
- `typer[all]>=0.12.0` - CLI framework with rich support
- (No other runtime dependencies needed)

**Development:**
- `pytest>=8.0` - Testing
- `pytest-cov` - Coverage
- `mypy` - Type checking
- `ruff` - Linting and formatting

### Testing Approach

1. **Unit tests**: Test individual functions in `core/`
2. **CLI tests**: Use Typer's `CliRunner` to test commands
3. **Integration tests**: Test full loop with mock Claude responses

Example CLI test:
```python
from typer.testing import CliRunner
from ralph.cli import app

runner = CliRunner()

def test_init_creates_ralph_directory(tmp_path):
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (tmp_path / ".ralph").exists()
```

### CI/CD Configuration

GitHub Actions with cross-platform matrix:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.10", "3.11", "3.12"]
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest --cov
      - run: mypy src/
      - run: ruff check src/
```

### Migration Path

1. **Phase 1**: Create Python project structure with Typer CLI
2. **Phase 2**: Port `ralph run` (current behavior) to Python
3. **Phase 3**: Add new commands (`init`, `status`, `reset`, `history`)
4. **Phase 4**: Add `.ralphignore` support
5. **Phase 5**: Deprecate `ralph.sh`, update documentation
6. **Phase 6**: (Optional) Add PyInstaller builds for binary distribution

### Known Trade-offs

1. **Requires Python**: Unlike Go/Rust binaries, users need Python. Mitigated by:
   - Python is pre-installed on macOS/Linux
   - PyInstaller can create standalone binaries if needed

2. **Larger "binary" if using PyInstaller**: ~50MB vs ~15MB for Go. Acceptable for a CLI tool.

3. **Slightly slower startup**: Python is slower to start than compiled languages. For a tool that runs Claude (which takes seconds), this is negligible.

---

## References

### CLI Frameworks
- [Typer Documentation](https://typer.tiangolo.com/)
- [Click Documentation](https://click.palletsprojects.com/)
- [Cobra (Go)](https://cobra.dev/) / [GitHub](https://github.com/spf13/cobra)
- [Clap (Rust)](https://docs.rs/clap/) / [GitHub](https://github.com/clap-rs/clap)

### Packaging & Distribution
- [PyInstaller](https://pyinstaller.org/) / [GitHub](https://github.com/pyinstaller/pyinstaller)
- [Deno Compile](https://docs.deno.com/runtime/reference/cli/compile/)
- [Bun Executables](https://bun.com/docs/bundler/executables)

### Testing
- [pytest Documentation](https://docs.pytest.org/)
- [shunit2 (Bash)](https://github.com/kward/shunit2)
- [Typer Testing](https://typer.tiangolo.com/tutorial/testing/)

### CI/CD
- [GitHub Actions Matrix Strategy](https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs)

### Claude Code Integration
- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)

---

## Appendix: Alternative Considered and Rejected

### Node.js

Not considered in detail because:
- Deno/Bun offer better single-binary story
- node_modules overhead
- No significant advantage over Python for this use case

### Ruby

Not considered because:
- Less common than Python
- No clear advantage
- Smaller CLI framework ecosystem

### Crystal / Nim / Zig

Not considered because:
- Too niche
- Small communities
- Limited library ecosystems
