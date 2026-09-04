# Dig

Dig keeps every project you are working on in one place: what stage each one is
at, what its next step is, and what you decided along the way. Ideas wait until
you start them. Everything stays on this computer.

It is for one person running several lines of work at once, apps, client work,
personal projects, content, programs, who wants to open one window and see where
everything actually stands.

Dig makes no outbound internet requests of any kind. There are no accounts and
there is no cloud. Sync is off by default, and when you turn it on it is a
direct connection between your own devices on your own private network, with
nothing passing through anyone else's servers.

## What it does

- **Projects and stages.** Every project has a type, and a type decides which
  stages it moves through and what each stage's checklist suggests. You decide
  when something moves. No boards, no dragging.
- **Next steps.** One line per project saying the single thing that moves it
  forward. Home shows the four that have been sitting longest.
- **Waiting on someone else.** Mark what a project is waiting for. Dig counts
  the days and never nags anyone.
- **A roadmap at every level.** Now, Next, Later, Someday, for everything or for
  one group.
- **Ideas.** Things you might make one day, with no stage and no deadline. Dig
  brings an old one back for a second look now and then.
- **Decisions.** Numbered, dated, permanent. Replaced ones stay visible, crossed
  out, so the reasoning survives.
- **Releases and files.** What shipped and when, and the documents that came
  with it, kept inside Dig.
- **Your week.** Written from what actually happened: stage changes, decisions,
  releases, and waits. If nothing moved, it says so.
- **Sharing.** A PDF of one project, of your projects, of the roadmap, or of the
  week. Private groups never appear, and every export says what was left out.

## What Dig is not

These are decisions, not gaps. Dig has no boards or drag and drop, no due dates
on tasks, no priorities, no assignees, no time tracking, no money or invoicing,
no notifications, no accounts or cloud, and no AI.

## Running it

Dig needs Python 3.11 or newer and PySide6 with QtWebEngine. On Bazzite and
other image based systems everything installs into your home folder; nothing is
written to `/usr` and nothing asks for root.

```
git clone https://github.com/Kamsiob/dig.git
cd dig
./install.sh
```

That creates a virtual environment (reusing a system PySide6 if there is one),
installs the icon and the launcher, and puts a `dig` command on your PATH. Then
launch Dig from your applications menu, or run `dig`.

`./uninstall.sh` removes the launcher, the icons, and the command. It never
touches your data.

## Keyboard

| | |
|---|---|
| Add something | <kbd>Ctrl</kbd> <kbd>K</kbd> |
| Find anything | <kbd>/</kbd> |
| Home | <kbd>1</kbd> |
| Projects | <kbd>2</kbd> |
| Roadmap | <kbd>3</kbd> |
| Ideas | <kbd>4</kbd> |
| Library | <kbd>5</kbd> |
| Your week | <kbd>6</kbd> |
| Close anything | <kbd>Esc</kbd> |
| Shortcuts | <kbd>?</kbd> |

## Your data

Everything lives in `~/.local/share/dig`: one SQLite file, the files you have
added, and a rolling set of recent saves for recovery. Export the whole thing as
JSON at any time from Settings, and bring it back the same way.

Dig follows your desktop's light or dark setting, and its reduce motion setting.

## Built by one person

Dig is made and carried by [Kamsiob](https://kamsiob.com).

[YouTube](https://youtube.com/@kamsiob) ·
[GitHub](https://github.com/kamsiob) ·
[Website](https://kamsiob.com) ·
[Telegram](https://t.me/+g5LKm9rUnNcxMjk5) ·
[hello@kamsiob.com](mailto:hello@kamsiob.com)

If software made this way matters to you, there is
[a place to stand behind it](https://buymeacoffee.com/kamsiob). Either way, it
is yours.

## License

AGPLv3. See [LICENSE](LICENSE). Free and open source.
