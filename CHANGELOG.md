# Changelog

## [1.8.20] - 2026-11-03
### Changed
- Synced the latest model and service files to GitHub and PythonAnywhere; `User`, `Subject` and `Task` now live in `models/`.

## [1.8.19] - 2026-11-03
### Changed
- Extracted the `Subject` model into `models/subject.py`; the database table and behaviour are unchanged.

## [1.8.18] - 2026-11-03
### Changed
- Extracted the `User` model into `models/user.py`; the database table name and all account behaviour are unchanged.

## [1.8.17] - 2026-11-03
### Changed
- Extracted timezone helpers into `services/time.py`; app timezone and today calculations are unchanged.

## [1.8.16] - 2026-11-03
### Changed
- Extracted the shared date parsing/formatting helpers into `services/dates.py`; phone and Australian date formats are unchanged.
- Test runner now runs every test file, not only the smoke file.

## [1.8.15] - 2026-11-03
### Changed
- Extracted task resource upload/download/delete routes into the Homework blueprint; all old URLs and endpoint names are preserved.

## [1.8.14] - 2026-11-03
### Changed
- Extracted the delete-task route into the Homework blueprint; `/delete-task/<id>` and the old endpoint are preserved.

## [1.8.13] - 2026-11-03
### Changed
- Extracted complete, uncomplete and Homework history routes into the Homework blueprint; all old URLs and endpoint aliases are preserved.

## [1.8.12] - 2026-11-03
### Changed
- Extracted edit-task and save-task-notes routes into the Homework blueprint; old URLs and endpoint names are preserved.

## [1.8.11] - 2026-11-03
### Fixed
- The extracted Homework task-detail route now has its lazy app helpers, restoring `/task/<id>`.

## [1.8.10] - 2026-11-03
### Changed
- Extracted the add-task and task-detail Homework routes into `blueprints/homework.py`; old `/add-task`, `/task/<id>` URLs and endpoint names are preserved.

## [1.8.9] - 2026-11-03
### Changed
- Extracted the Homework list route into `blueprints/homework.py`; `/tasks` and the old `tasks` endpoint remain available.

## [1.8.8] - 2026-11-03
### Changed
- Extracted the Today dashboard route into `blueprints/today.py`; the old `/today` URL and `today_page` endpoint are preserved through a compatibility alias.
### Verified
- 30-day login cookie survives a fresh browser session in the automated test.

## [1.8.7] - 2026-11-03
### Fixed
- Phone top bar now sits in normal page flow, so it cannot cover the page title or greeting.
- Phone sidebar wordmark is smaller and clear of the close button.

### Added
- “Keep me logged in for 30 days” on the login form.

## [1.8.6] - 2026-11-03
### Added
- “Keep me logged in for 30 days” checkbox on login. Ticked sessions use a 30-day permanent cookie; unticked sessions still end when the browser closes.
### Fixed
- Phone sidebar wordmark no longer runs under the close button.

## [1.8.5] - 2026-11-03
### Fixed
- Desktop sidebar wordmark fits the full SmartStride name without clipping.

## [1.8.4] - 2026-11-03
### Changed
- Phone Calendar now opens with the calendar above reminder/help cards, full-width action buttons, shorter day cells and a clear top app bar. Tablet keeps a split sidebar/content layout; the sidebar wordmark now fits smaller widths.

## [1.8.3] - 2026-11-03
### Changed
- Responsive layout pass: full-width phone layout with a fixed top bar and slide-over menu; split sidebar + content on iPad/tablet; compact sidebar on small laptops; wider workspace on desktop.

## [1.8.2] - 2026-11-03
### Changed
- Moved the legacy `/signup` redirect into the auth blueprint while keeping the old URL and `signup` endpoint working.

## [1.8.1] - 2026-11-03
### Changed
- Rebranded the product from Study OS to **SmartStride** across pages, buttons, descriptions, print views, share pages, PWA manifest and notifications.

## [1.8.0] - 2026-11-03
### Added
- Installable home-screen PWA: manifest, icons, standalone display and iPhone safe-area support.
- Service-worker registration on all signed-in pages.

## [1.7.1] - 2026-11-03
### Changed
- Moved email verification routes into the auth blueprint. Existing URLs still work.

## [1.7.0] - 2026-11-03
### Added
- Collapsible desktop sidebar with icon-only mode and saved state.
- Mobile drawer navigation with menu button, close button and backdrop.
- Responsive sidebar layout for laptop, desktop, iPad and phone widths.
### Changed
- Moved password reset routes into the auth blueprint; existing URLs still work.

## [1.6.8] - 2026-11-03
### Changed
- Moved register into `blueprints/auth.py` with a compatibility endpoint. No visible behaviour change.

## [1.6.7] - 2026-11-03
### Changed
- Moved login into `blueprints/auth.py` with a compatibility endpoint for existing templates. No visible behaviour change.

## [1.6.6] - 2026-11-03
### Changed
- Moved logout into `blueprints/auth.py`; the visible Log out link still works.

## [1.6.5] - 2026-11-03
### Changed
- Moved the health endpoint into `blueprints/health.py` and registered it through the app. Same URL, no behaviour change.

## [1.6.4] - 2026-11-03
### Changed
- Extracted the shared database object into `extensions.py`. No behaviour changes.

## [1.6.3] - 2026-11-03
### Changed
- Extracted application paths and secret loading into `config.py`. No behaviour changes.

## [1.6.2] - 2026-11-03
### Added
- Phase 0 health endpoint at `/healthz`.
- Environment-selectable database path for staging and tests (default unchanged).

## [1.6.1] - 2026-11-03
### Added
- Print pages now have Week view / Month view switches, so you can print either from the same place.

## [1.6.0] - 2026-11-03
### Changed
- Home dashboard now says “Welcome to Study OS, NAME”.

## [1.5.9] - 2026-11-03
### Added
- New display and handwritten fonts: Fraunces, Playfair Display, Lora, Cormorant Garamond, DM Sans, Sora, Nunito, Quicksand, Space Grotesk and Caveat.

## [1.5.8] - 2026-11-03
### Fixed
- Settings now loads the signed-in account's saved appearance instead of the previous browser defaults.
- Switching accounts no longer overwrites the new account's wallpaper/theme on the Settings page.

## [1.5.7] - 2026-11-03
### Changed
- Dashboard greeting now says “Welcome to Study OS, NAME”.

## [1.5.6] - 2026-11-03
### Fixed
- Appearance is now isolated per account. Switching accounts no longer reuses the previous account's wallpaper, theme or font from browser storage.
- Logged-in pages always use the appearance saved on the server for that account.

## [1.5.5] - 2026-11-03
### Fixed
- Login accepts either the email or the account username as a fallback.
- Removed the login lockout message.
- Synced latest appearance settings and database to PythonAnywhere.

## [1.5.4] - 2026-11-03
### Fixed
- Removed the 15-minute login lockout. Login attempts are no longer rate-limited.
- Synced the latest database to PythonAnywhere so the latest account password, appearance and data are present.

## [1.5.3] - 2026-11-03
### Changed
- Levels expanded from 15 to 30, with new titles and higher XP thresholds.
- The level ladder is collapsible and scrolls.
- New XP boost tiers at levels 16, 20, 24 and 28.

## [1.5.2] - 2026-11-03
### Changed
- Removed the badge/prize ladder. Levels now show titles and XP boosts only.
- Removed badges from the sidebar, Today and Recap.

## [1.5.1] - 2026-11-03
### Fixed
- More Chinese coverage on Subjects, Today and Grades: subject homework counts, XP summaries, streaks, prizes, result averages and chart dates.

## [1.5.0] - 2026-11-03
### Added
- Web Push desktop reminders: works when the StudyOS tab is closed, with a service worker and click-through to today’s calendar.
- View reminders list on the Calendar.
- Push subscriptions stored per account and checked every 30 seconds by the server.

## [1.4.11] - 2026-11-03
### Changed
- Finished Chinese translations on Levels, Pomodoro, the study helper and dynamic XP/streak labels.
- Reworded the Pomodoro intro and level summary in Chinese.

## [1.4.10] - 2026-11-03
### Changed
- Calendar reminders moved out of the crowded toolbar into a clean reminder bar with one toggle and a test button.

## [1.4.9] - 2026-11-03
### Changed
- Login now asks for email only, not username.
- Register page rebuilt to match the login design; show/hide password and client-side password-match check.
- Flash messages restyled as subtle inline cards instead of raw top-of-page text.

## [1.4.8] - 2026-11-03
### Added
- Share tab in the sidebar.
- Test reminder button and in-page reminder toast on the Calendar; browser reminders now check 30 days.
- Register page rebuilt to match the login page, with show/hide password and live password-match validation.
### Changed
- Removed Create planner link from Sharing.
- Expanded Chinese translations for settings, dropdowns, level titles, appearance and sidebar labels.

## [1.4.7] - 2026-11-03
### Added
- Back button on all print pages, returning to the Calendar.

## [1.4.6] - 2026-11-03
### Fixed
- Weekly planner always opens on the current week.
- Monthly calendar always opens on the current month.
- Previous/Next are the only way to move away from the current week or month.

## [1.4.5] - 2026-11-03
### Changed
- Weekly planner rebuilt around one connected week: summary counts, integrated day-by-day events/homework/assessments/to-dos, automatic fallback to the latest useful week, and assessment countdown.
- Assessment timetable rebuilt: upcoming, undated and completed sections, clear empty state, due dates, countdowns and next actions, plus all calendar events.
### Fixed
- Removed the remaining old email-code endpoints; email changes use current password + new email twice.

## [1.4.4] - 2026-11-03
### Changed
- Printable monthly calendar opens on the latest month with calendar events or assessments, so the page is not blank in the current month.
- Calendar cells and text are sized better for A4 landscape printing.

## [1.4.3] - 2026-11-03
### Added
- Parent / teacher summary now includes overall average, subject averages, recent grades, this-week and all-time study time.
- Resource pack now includes files from Resources, assessment attachments and homework attachments.
### Changed
- Active share links and group checklists can be collapsed and scroll inside their cards.

## [1.4.2] - 2026-11-03
### Added
- A printable monthly calendar timetable (`/print/calendar`) with all homework, to-dos, assessments and events, plus Previous/Next month.
### Fixed
- Grade goal now fills in your real Grades page average and shows how many assessments it uses.
- Print assessment pages say clearly when there are no assessments, and show due dates when there are.

## [1.4.1] - 2026-11-03
### Changed
- Greeting is now simply “Hello” at all times.
- The current level badge is shown clearly on Today and Recap.

## [1.4.0] - 2026-11-03
### Changed
- Weekly planner and assessment timetable rebuilt: cleaner layout, status badges, all assessments and all calendar events.
- Print pages no longer hide completed assessments or older calendar events.

## [1.3.5] - 2026-11-03
### Fixed
- Gradient accents are applied from the active body class as well, so real buttons show the gradient even when the stored accent value is stale.

## [1.3.4] - 2026-11-03
### Changed
- Pastel dream theme and pastel accents are softer, with dark readable text.

## [1.3.3] - 2026-11-03
### Changed
- Pastel accents are softer and lighter, with darker text so buttons stay readable.

## [1.3.2] - 2026-11-03
### Changed
- Level curve is less instant: Level 2 needs 80 XP, Level 10 needs 2,700 XP.
- Level badges now display; animated ring from Level 9, gold badge from Level 10, recap highlight from Level 7.

## [1.3.1] - 2026-11-03
### Fixed
- Gradient accents now override the solid accent rule and apply to real buttons on every page.

## [1.3.0] - 2026-11-03
### Changed
- Email sending removed from Settings. New accounts confirm by re-entering their email and current password; changing email uses current password + new email twice.

### Fixed
- Gradient accents are applied directly to buttons so they work even with a cached stylesheet.

## [1.2.0] - 2026-11-03
### Added
- Better level titles and real prizes: badges, per-level XP boosts, recap highlight and animated ring.
- Back button on the Levels page.

## [1.1.0] - 2026-11-03
### Added
- Recap page redesigned to match StudyOS: hero, stat cards, subject bars, quests, next week and level card.

### Fixed
- Old check-ins saved with the UTC date are moved to the correct Melbourne date, so Today shows them as done.
- Appearance choices now save on the server as well as the browser.

## [1.0.6] - 2026-11-03
### Removed
- Kawaii cat removed from the theme list as well.

## [1.0.3] - 2026-11-03
### Added
- Eight pastel accent colours and four gradient accents.

## [1.0.2] - 2026-11-03
### Fixed
- Appearance preview now matches the final clean frames and refreshes with a new cache version.
- Removed the Kawaii cat frame from the frame list.

## [1.0.0] - 2026-11-03
### Changed
- All theme and frame types are listed again and independently changeable.
- Frames are now clean coloured borders with one small motif (cat ears, blossom, leaf sprig) and no repeating patterns.
- Frames keep a real gap around the sidebar and page content.
- Changing wallpaper also adjusts font, theme and accent for legibility.

## [0.9.6] - 2026-11-03
### Fixed
- Frames now keep a clear margin around the sidebar and page content instead of touching them.

## [0.9.5] - 2026-11-03
### Changed
- Removed the Sakura/Floral frame and theme. Changing wallpaper now also adjusts font, theme and accent so text stays legible.

## [0.9.4] - 2026-11-03
### Fixed
- Old saved Kawaii/Forest/Pastel appearances now fall back to a clean look instead of showing removed styles.

## [0.9.3] - 2026-11-03
### Removed
- Removed the custom wallpaper upload section and the “My uploaded picture” option.

## [0.9.2] - 2026-11-03
### Changed
- Removed Forest, Kawaii cat and Pastel dream themes and the Kawaii cat frame. Appearance keeps seven clean ready-made looks.

## [0.9.1] - 2026-11-03
### Changed
- Appearance has one “Ready-made looks” gallery instead of two overlapping preset rows. Curated to nine complete looks; each applies theme, frame, wallpaper, font and accent.

## [0.9.0] - 2026-11-03
### Added
- New accounts must confirm their email before login. A pending page can resend the verification email.
- Password reset uses a masked email challenge (first two and last five characters).

### Changed
- Settings and login no longer show “email is not configured” messages.

## [0.8.1] - 2026-11-03
### Added
- Password reset now uses a masked-email challenge: first two and last five characters are shown; enter the full email to continue to a new password.
- SMTP sending supports TLS and SSL (port 465) with a timeout.

### Changed
- Removed “email is not configured” wording from Settings and verification pages.

## [0.8.0] - 2026-11-03
### Changed
- Theme gallery is now visual cards; each card applies theme, frame, wallpaper, font and accent together.
- Kawaii frame is a paw-print border with cat ears; Sakura is a blossom border; Botanical is a leaf border.
- Today page is livelier with a level ring, momentum meter, quick actions and claimable quests.
- Grade goal rebuilt with a gauge, breakdown and plain verdict.
- Inbox rebuilt as a compact “give these a date” list.
- Removed the Study activity chart from Weekly recap.

### Fixed
- Confetti now survives the page reload after completing something.
- Greeting uses Melbourne time (morning is morning).
- Sidebar “TOOLS” changed to “Tools”.
- Print pages have print buttons; timetable includes calendar events.

## [0.7.1] - 2026-11-03
### Changed
- Removed the Study activity chart from Weekly recap; it was not useful.

### Fixed
- Greeting and Today date now use Australia/Melbourne time, not UTC.
- Share/planner/summary/resource links use the public Codespace URL and the port is public for parents/tutors.
- Public share pages and checklists have a “← StudyOS” link back.
- Print pages have a Print / Save as PDF button; timetable includes calendar events.

## [0.7.0] - 2026-11-03
### Added
- Today dashboard redesigned: level ring, XP progress, streak, momentum meter, quick actions, claimable quests and a daily bonus.
- Levels page explaining XP sources, titles, level ladder and what happens on level-up.
- Grade goal calculator rebuilt with a clear answer, gauge, calculation breakdown and realistic verdict.
- Printable weekly planner and assessment timetable now have a Print / Save as PDF button; timetable includes calendar events.
- Print button on Calendar and a print stylesheet that hides navigation.
- Sample CSV downloads on the import page.

### Changed
- Smart Inbox rebuilt as a compact “give these a date” list.
- Weekly recap replaces the heatmap with seven clear daily bars and counts.
- Share links now use the public Codespace URL; the port is public so parents/tutors can open links without an account.
- Public share pages and group checklists have a “← StudyOS” link back.

### Fixed
- CSV import/export verified; sample files work.
- Resource pack links use the same public URL as planner and summary links.

## [0.6.3] - 2026-11-03
### Changed
- Removed the dashboard customiser; it was confusing and not useful. The dashboard is fixed and predictable.
- Frames now show clear themed corner art: cat faces for Kawaii, cherry blossoms for Sakura/Floral, leaf sprigs for Botanical.

## [0.6.2] - 2026-11-03
### Fixed
- Finishing a Pomodoro now saves completion, XP and heatmap/quest progress.

## [0.6.1] - 2026-11-03
### Added
- Full Simplified Chinese coverage for static interface text, placeholders and common dynamic labels, with live re-translation for calendar/date content.

### Fixed
- Home “Customise” button now works: its script was accidentally inside the page title block and never ran.
- Uploaded wallpaper now applies immediately and on every later page.
- Chinese mode now translates dynamic labels such as Level, streaks, quest progress and Pomodoro counts.
- Frames redesigned as clean borders with one motif; Kawaii now has cat ears and one small cat face instead of dense cats.

## [0.6.0] - 2026-11-03
### Changed
- Renamed Panorama to Pomodoro everywhere (it is a Pomodoro timer: study blocks, breaks, cycles, music). Old /panorama link redirects.
- Removed the separate Focus mode; Pomodoro is now the only study timer.
- Redesigned the weekly recap heatmap: last 8 weeks, weekday labels, one square per day, explicit 0/1/2–3/4–5/6+ legend and an active-days summary.
- Frames simplified: clean coloured border plus one small motif (cat ears for Kawaii, blossom for Floral/Sakura, leaf sprig for Botanical). No more repeating patterns.

### Fixed
- Home “Customise” button now works (its script was in the page title block, so it never loaded).
- Uploaded wallpaper now applies automatically after upload.
- Pomodoro completion is recorded for XP, quests and the heatmap.

## [0.5.1] - 2026-11-03
### Fixed
- Patterned frames now match their names: Botanical has leaves and flowers, Floral has flowers, Kawaii has cat faces, Soft is a dotted accent ring.
- Frames moved into the page margin so they no longer cover sidebar text.
- Added cache-busting to CSS/JS and no-store on HTML so changes appear on a normal refresh.
- Deployed to the live Codespace (not just a local copy) and verified there.

## [0.5.0] - 2026-11-03
### Added
- Today dashboard with overdue, due-today, next-three-days, to-dos and a workload suggestion.
- Assessment countdown with a next action for each assessment, on Home and Today.
- Smart Inbox for homework and assessments missing a date or subject.
- Grade goal calculator with a clear required-mark result and reachability check.
- Daily quests, XP and levels, daily check-in with streak, weekly recap and a 16-week study heatmap.
- Focus mode with a full-screen timer, presets and automatic session logging.
- Subject icons and colours across homework, assessments and subject pages.
- Customisable home dashboard: show, hide and reorder widgets.
- Pinned “next three” tasks on the home dashboard.
- Dark mode, 18-theme gallery, custom wallpaper upload and per-subject accent colours.
- CSV export and import for homework, assessments, grades and to-dos.
- Print/PDF weekly planner and assessment timetable.
- Archive instead of delete, Trash with restore, version history with undo and an audit log.
- Read-only planner links, parent/tutor weekly summaries, resource pack links and shared study-group checklists.
- English/Chinese interface switch for the main navigation and common interface labels.

### Removed
- First-run setup wizard and “Try demo workspace” were removed completely. New accounts go straight to the dashboard.

### Changed
- Quick add now explains that it only adds homework, needs the subject, homework name and a day or date, and saves an unknown subject under “No Subject”.

### Fixed
- Appearance preview now uses the selected accent colour instead of the theme's default.
- Frame preview now shows every frame distinctly, including cat ears for the Kawaii frame.
- Kawaii cat uses a real cat wallpaper (cats, not only paw prints).
- “Match theme colours” now also changes the font to match the theme.
- Wallpapers have stronger, clearer repeat patterns and work on dark mode.
- Page frames sit above page content and stay visible on every page.

All notable changes to StudyOS are recorded here.
Versioning: Semantic Versioning (`MAJOR.MINOR.PATCH`).
- PATCH: fixes and small visual tweaks
- MINOR: new features or new options
- MAJOR: breaking changes or data migrations

## [0.4.1] - 2026-11-02
### Added
- Settings link to reopen the setup wizard for existing accounts.

### Fixed
- Frames now render as a page-level overlay and cannot be hidden by page content.

## [0.4.0] - 2026-11-02
### Added
- First-run setup wizard for year level, subjects and the first assessment.
- Demo workspace button with sample subjects, homework, assessments and a to-do.
- Home quick-add bar with simple natural-language dates and subject matching.

### Changed
- New accounts are sent to the setup wizard after registration/login.

## [0.3.8] - 2026-11-02
### Fixed
- Frames are now drawn as a fixed page-level overlay instead of a border inside the content area, so they cannot be hidden by page layouts.
- Added a visible frame indicator to the appearance preview label.

## [0.3.7] - 2026-11-02
### Added
- Curated style presets: Clean, Soft paper, Botanical, Sakura, Kawaii cat, Pastel dream, Ocean and Microsoft.
- Kawaii cat and Pastel dream themes, with coordinated buttons, headings and frames.
- Appearance changes now save automatically as well as updating the live preview.

### Fixed
- Preview font now follows the selected font reliably.
- Preview continues to mirror theme, wallpaper, frame and accent.

## [0.3.6] - 2026-11-02
### Added
- Desktop calendar reminders at 15, 10 and 5 minutes before timed calendar events.
- Calendar page button to enable/disable browser notifications; reminders refresh while StudyOS is open.

### Notes
- Browser notifications require permission and the StudyOS tab to remain open. Closed-browser push notifications need a hosted PWA/push service.

## [0.3.5] - 2026-11-02
### Fixed
- Selected fonts now apply across the whole app, not only some headings; page-specific font declarations no longer override the choice.
- Appearance preview uses the selected font consistently.

## [0.3.4] - 2026-11-02
### Fixed
- Wallpaper motifs are visible again; flowers, leaves, paws, swirls, stars, hearts, clouds and waves use a neutral contrasting motif colour.
- Appearance preview mirrors font, theme, accent, wallpaper and frame, and changes apply to the page immediately.

## [0.3.3] - 2026-11-02
### Fixed
- Appearance preview now updates for font, theme, accent, wallpaper and frame changes.
- Frame changes are mirrored in the preview and applied to the real page.

## [0.3.2] - 2026-11-02
### Added
- Email sending configuration in Settings: SMTP server, port, username, password, from address, TLS and test email.
- Email-change verification code is now emailed to the new address when SMTP is configured; otherwise it is shown in-app.

### Changed
- Email changes mark the new address as verified and login accepts the new email immediately.
- Removed the misleading "login username stays the same" text from the profile card.

## [0.3.1] - 2026-11-02
### Changed
- Rebuilt the login page as a responsive split-screen layout with a branded panel, cleaner form spacing and clearer hierarchy.
- Login now reads the saved font and accent/theme colours from Settings, so it matches the rest of the app.
- Kept the show/hide password control and remove-forgot-password link policy.

## [0.3.0] - 2026-11-02
### Added
- Appearance live preview in Settings, showing the selected theme, font and accent before saving.
- Optional page frames: Soft, Kawaii cat, Botanical, Floral and Classic.
- Reset to default button for all appearance choices.

### Changed
- Themes and wallpapers are independent layers; choosing a theme no longer replaces the wallpaper.
- Redesigned the Aurora wallpaper as a layered iridescent gradient.
- Expanded fonts, themes, wallpapers and accent colours.

### Fixed
- Theme background shorthand was overriding wallpaper images.
- Notebook theme no longer forces its own ruled-paper background over the selected wallpaper.
- Outlook theme no longer hides the wallpaper inside the main content area.
