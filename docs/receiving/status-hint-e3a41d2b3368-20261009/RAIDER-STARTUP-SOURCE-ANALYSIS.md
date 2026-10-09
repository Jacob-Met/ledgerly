# Raider startup: source-only diagnosis

**The actual cause remains unestablished.** The single run preserved at [5765bc24](https://github.com/Jacob-Met/ledgerly/blob/5765bc2489a4c753ac99684b9a5d46f09a4edaa0/docs/receiving/status-hint-e3a41d2b3368-20261009/README.md) failed before private CDP admission: 31 private HTTP asset matches, zero browser responses and zero application groups. This note explains what matching primary source can and cannot add. No runtime, flag, policy, installation, profile, provider or capacity probe was made during this analysis.

## Primary version binding

The official `chromium/chromium` Git tag `154.0.8037.97` was directly read as commit **`b510e9d7cd3a2fbd78d0ddc42234103206c5f78d`**. The version matches the retained Chrome executable's product metadata. It does not independently bind an actually loaded Chrome DLL, effective feature state, token or successful Browser.getVersion response; those were not captured before startup stopped.

| Primary file at the exact commit | Git blob |
| --- | --- |
| [Windows browser startup](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/browser/chrome_browser_main_win.cc) | `37b7ad5300599a4de008175c3c535d1ff63c5398` |
| [Browser feature defaults](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/browser/browser_features.cc) | `123db77799e8e4ff5d34fac0db8ed8ca69f2e860` |
| [ChromeDriver launcher](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/test/chromedriver/chrome_launcher.cc) | `e99f0c78dda3c20470d7018060469797933ad7f1` |
| [Normal result classification](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/common/chrome_result_codes.cc) | `18d4131d9122159e81dc1dfc9a48d5711e8a271a` |
| [ChromeMain result conversion](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/app/chrome_main.cc) | `199142d67135ea46b9aa232c0283ad7d21f7b3f1` |
| [Windows executable entry](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/app/chrome_exe_main_win.cc) | `5f9fa297f680b83b4c8757a56a928fc3380be1fb` |
| [Main startup delegate](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/app/chrome_main_delegate.cc) | `b8eeec779ce30b20cc550f12cfda599c4604ced3` |
| [De-elevation implementation](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/base/win/elevation_util.cc) | `2135c507b80f17d0073238cb2ae28e13878267dd` |

## What exit 0 permits

`PreEarlyInitialization` can relaunch an old browser version or request automatic de-elevation. The latter requires its feature to be enabled and an unnecessarily elevated linked token; it excludes integration tests and checks automation/relaunch switches. A successful de-elevation launch returns a distinct internal normal-exit result. These are conditional code paths, not evidence that this host took either path. [Windows startup](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/browser/chrome_browser_main_win.cc)

The result classifier includes upgrade relaunch, process notification and automatic de-elevation among normal early exits. `ChromeMain` converts such results to the ordinary normal exit code. Consequently, observed launcher exit 0 does not distinguish ordinary completion from those classified early exits. [Classification](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/common/chrome_result_codes.cc) · [Conversion](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/app/chrome_main.cc)

The captured Ledgerly argv lacks `--enable-automation`. The same-version ChromeDriver common switch list includes it, while the Windows de-elevation guard explicitly treats it as an automation exception. This is a concrete declared-launch difference. The feature is enabled by default in source, but default source state is not proof of the effective feature or token state in this run. No flag change was selected or executed from this observation. [ChromeDriver](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/test/chromedriver/chrome_launcher.cc) · [Windows guard](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/browser/chrome_browser_main_win.cc) · [Default](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/browser/browser_features.cc)

## Two useful exclusions and a retained failure

The executable's earliest fast-notification path permits only the profile-directory switch and rejects multiple/non-fast switches. The recorded command contains many other switches; that narrow path does not explain the recorded argv under the inspected parser contract. This does not exclude later process-singleton notification. [Executable entry](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/app/chrome_exe_main_win.cc)

The exact-tag isolated-browser startup path waits for the isolated browser's exit and returns its exit code. A generic claim that every isolated-browser stub immediately returns while its real browser continues would misdescribe this source. No isolated-launch state or process-role binding was captured here. [Startup delegate](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/app/chrome_main_delegate.cc)

ChromeDriver itself stops startup when its launched process has terminated before DevTools readiness, including normal exit, and asks for diagnostic logs. Our early stop is therefore consistent with the maintained launcher's failure policy. Merely ignoring exit or increasing the wait would not establish a correct browser session or ownership. Empty captured logs likewise do not identify a cause. [ChromeDriver](https://github.com/chromium/chromium/blob/b510e9d7cd3a2fbd78d0ddc42234103206c5f78d/chrome/test/chromedriver/chrome_launcher.cc)

## Receipt limits and decision

The retained supervisor recorded exact Node exit/handle closure and three remaining job associations before closing the job. It did not record those processes' browser roles or successful CDP identity. The driver removed its own profile after the initial Chrome child exited; the independent later scoped query established that the seven known PIDs/direct children and profile were absent. Preserve that ordering and narrow observation, rather than treating the initial child exit as complete tree closure.

No further launch, capacity poll, logging campaign, feature override, de-elevation override or sandbox change follows this note. The original application and supervisor failures remain failures; the native source qualification and immutable old public PASS remain unchanged. A future independent receiver design would need an explicit maintained automation launch contract and browser/owned-process identity before application actions, plus cleanup tied to owned-process closure. That is a design boundary, not a claim that adding one flag fixes the observed failure.
