# Changes to sample data

Two kinds of change were made to unlabelled sample files, plus nothing else.

## 1. Email domains moved to reserved names

Every email address in the sample CSVs now uses a reserved domain. The part
before the @ is unchanged, and the same old domain always maps to the same new
one:

| Old domain | New domain |
|---|---|
| gmail.com | example.com |
| outlook.com | example.org |
| fastmail.com | example.net |
| icloud.com | icloud.example |
| hey.com | hey.example |
| mailinator-example.org | mailinator.example |
| example-corp.dev | example-corp.example |

`inbox.example` was already a reserved name and was left as it is.
`sort-from-a-handful/examples/github_issues/` holds real public data and was
not touched. `labelled_sample.csv` files, `questions.csv`, `hard_cases.csv`,
`items.csv`, `corrections.csv` and `sorted.csv` contain no email addresses and
were not touched.

## 2. Broken templated rows rewritten in natural English

The generator that built the sample CSVs wrapped every topic phrase in short
restate templates. Applied to a full sentence, several templates produce broken
English, for example:

> Can we get the AI panel was the best session of the event, more like that
> please? I hit this every week

Each such row was rewritten to the same sentence on its own, with the template
words dropped. Typos already in the row were kept, and trailing asides such as
"I hit this every week" were kept where they still read as something a person
would write. Templates that read naturally on a sentence (Me too, Same here,
Agreed, +1, "Third time asking:" on a request, "please and thank you",
"same as everyone else here", "Every single day this comes up") were left alone.

Row counts fixed, by file:


| File | Rows fixed |
|---|---|
| what-people-ask-for/examples/event_feedback/event_feedback.csv | 86 |
| what-people-ask-for/examples/feature_requests/feature_requests.csv | 166 |
| what-people-ask-for/examples/product_reviews/product_reviews.csv | 55 |
| what-people-ask-for/examples/support_tickets/support_tickets.csv | 62 |
| **Total** | **369** |

No row in a labelled or question file was changed. The full row list follows.

### what-people-ask-for/examples/event_feedback/event_feedback.csv

| Row id | Before | After |
|---|---|---|
| E0001 | Would love please upload the slides, even just PDFs would help | Please upload the slides, even just PDFs would help. |
| E0003 | Honestly fruit and something not fried at breaks please, it was all pastries would fix most of my days I would use it every single day | Fruit and something not fried at breaks please, it was all pastries. I would use it every single day |
| E0007 | Would love please record the keynotes at minimum, the room was too full both times | Please record the keynotes at minimum, the room was too full both times. |
| E0008 | captions on screens would help, the echo made wrods hard to catch and I stop complaining I would use it every single day | Captions on screens would help, the echo made wrods hard to catch. I would use it every single day |
| E0009 | Would love registration staff were lovely but only two desks were open at 8am | Registration staff were lovely but only two desks were open at 8am. |
| E0012 | the panels went off topic, tighter moderation please please, iit is 2026 | The panels went off topic, tighter moderation please. |
| E0020 | Can we get the projector resolution was low, code samples were unreadable? | The projector resolution was low, code samples were unreadable. |
| E0030 | Would love the clash between the data track and the product track was painful | The clash between the data track and the product track was painful. |
| E0043 | Adding speed networking would have been useful, wandering the hall is not for veryone would help a lot we benchmark every tool against this | Speed networking would have been useful, wandering the hall is not for veryone. We benchmark every tool against this |
| E0046 | please add a shuttle from the station, the walk with luggage was grim in the rain would make my week it came up in our retro again | Please add a shuttle from the station, the walk with luggage was grim in the rain. It came up in our retro again |
| E0049 | Would love the security talk was excellent, concrete and no fluff | The security talk was excellent, concrete and no fluff. |
| E0050 | Can we get vegetarian options were an fterthought, one lukewarm pasta tray? | Vegetarian options were an fterthought, one lukewarm pasta tray. |
| E0052 | Any chance of check in took forever, the barcode scanner failed on half the badges? | Check in took forever, the barcode scanner failed on half the badges. |
| E0062 | some speakers read slides word for word, coach them or pick better ones and I stop complaining | Some speakers read slides word for word, coach them or pick better ones. |
| E0064 | Honestly some speakers read slides word for word, coach them or pick better ones would fix most of my days | Some speakers read slides word for word, coach them or pick better ones. |
| E0065 | Can we get the security talk was excellent, concrete and no fluff? we benchmark every tool against this | The security talk was excellent, concrete and no fluff. We benchmark every tool against this |
| E0071 | Adding lightning talks were the highlight, add a second lightning session would help a lot | Lightning talks were the highlight, add a second lightning session. |
| E0088 | Would love the venue stairs were a bottleneck, please plan room chanes ebtter it is the main gap for us | The venue stairs were a bottleneck, please plan room chanes ebtter. It is the main gap for us |
| E0089 | Honestly i came alone and left without meeting anyone, some structure would help would fix most of my days | I came alone and left without meeting anyone, some structure would help. |
| E0096 | Can we get the sponsor session felt like a sales pitch, mark it clearly or cut it? | The sponsor session felt like a sales pitch, mark it clearly or cut it. |
| E0098 | please split attendee wifi from presentation wifi, demos kept fainlig is all I want my whole team wants this | Please split attendee wifi from presentation wifi, demos kept fainlig. My whole team wants this |
| E0099 | Honestly slides please, half the talks refernced links we could not write down fast enough would fix most of my adys | Slides please, half the talks refernced links we could not write down fast enough. |
| E0100 | slides please, half the talks referenced links we could not write down fast enough please, it is 2026 | Slides please, half the talks referenced links we could not write down fast enough. |
| E0106 | Third time asking: two talks I cared about ran simultaneously, publish recordings please my whole team wants this | Two talks I cared about ran simultaneously, publish recordings please. My whole team wants this |
| E0117 | will the workshops be shared as videos? Some of us had to pick one of three would make my week my whole etam wants this | Will the workshops be shared as videos? Some of us had to pick one of three. My whole etam wants this |
| E0120 | Would love please arrange overflow parking, the venue lot held a fraction of the cars three of my colleagues asked the same | Please arrange overflow parking, the venue lot held a fraction of the cars. Three of my colleagues asked the same |
| E0122 | Any chance of the AI panel was the best session of the event, more like that please? we benchmark every tool against this | The AI panel was the best session of the event, more like that please. We benchmark every tool against this |
| E0129 | not enough breaks between sessions, 10 minutes is not enough to cross the venue please, it is 2026 three of my colleagues asked the same | Not enough breaks between sessions, 10 minutes is not enough to cross the venue. Three of my colleagues asked the same |
| E0137 | the name badge printer was out of one colour ribbon, badges looked half printed please, it is 2026 | The name badge printer was out of one colour ribbon, badges looked half printed. |
| E0143 | Can we get lighnting talks were the highlight, add a second lightning session? | Lighnting talks were the highlight, add a second lightning session. |
| E0144 | Third time asking: lunch seating was random, topic tables would help people meet | Lunch seating was random, topic tables would help people meet. |
| E0147 | Any chance of vegetarian options were an afterthought, one lukewarm pasta tray? | Vegetarian options were an afterthought, one lukewarm pasta tray. |
| E0150 | Can we get four tracks at once is too many for one person, record everything at least? my whole team wants this | Four tracks at once is too many for one person, record everything at least. My whole team wants this |
| E0152 | Any chance of the mics in track C cut out constantly, questions from the floor were lost? my whole team wants this | The mics in track C cut out constantly, questions from the floor were lost. My whole team wants this |
| E0160 | please label allergens on the lunch buffet, I spent ten minutes reading packets would make my week my whole team wants this | Please label allergens on the lunch buffet, I spent ten minutes reading packets. My whole team wants this |
| E0166 | Honestly the food was cold by the time our session let out, stagger lunch with tracks would fix most of my days I would use it every single day | The food was cold by the time our session let out, stagger lunch with tracks. I would use it every single day |
| E0167 | Third time asking:  Gluten free option was a single sad salad, please do better next year | Gluten free option was a single sad salad, please do better next year. |
| E0169 | Adding i gave up on my coat halfway through, then needed it again after lunch, the room temperature was all over the place would help a lot we benchmark every tool against this | I gave up on my coat halfway through, then needed it again after lunch, the room temperature was all over the place. We benchmark every tool against this |
| E0174 | Can we get i gave up on my coat halfway through, then needed it again after lunch, the room temperature was all over the place? | I gave up on my coat halfway through, then needed it again after lunch, the room temperature was all over the place. |
| E0175 | halal options were missing entirely, my colleague ate plain rice and I stop complaining it is the main gap for us | Halal options were missing entirely, my colleague ate plain rice. It is the main gap for us |
| E0176 | please add a second screen at the back, half the room could not see the demos would make my week I would use it every single day | Please add a second screen at the back, half the room could not see the demos. I would use it every single day |
| E0177 | air conditioning was pointed straight at the front rows, three people moveed is all I want | Air conditioning was pointed straight at the front rows, three people moveed. |
| E0179 | Adding the directions sent said parking was on the west side, it was east would help a lot this blocks our rollout | The directions sent said parking was on the west side, it was east. This blocks our rollout |
| E0182 | the car park was full by 9am, late arrivals drove around for half an hour and I stop complaining | The car park was full by 9am, late arrivals drove around for half an hour. |
| E0183 | Honestly hall A was boiling in the afternoon, people were fanning themselves with programmes would fix most of my days three of my colleagues asked the same | Hall A was boiling in the afternoon, people were fanning themselves with programmes. Three of my colleagues asked the same |
| E0191 | the security talk was excellent, concrete and no fluff please, it is 2026 I hit this every week | The security talk was excellent, concrete and no fluff. I hit this every week |
| E0193 | the workshop rooms had no power strips, laptops died mid exercise would make my week we benchmark every tool against this | The workshop rooms had no power strips, laptops died mid exercise. We benchmark every tool against this |
| E0200 | more breaks for chatting please, the schedule was wall to wall would make my week my whole team wants this | More breaks for chatting please, the schedule was wall to wall. My whole team wants this |
| E0210 | not enough breaks between sessions, 10 minutes is not enough to cross the venue and I stop complaining | Not enough breaks between sessions, 10 minutes is not enough to cross the venue. |
| E0214 | Honestly  Gluten free option was a single sad salad, please do better next year would fix most of my days | Gluten free option was a single sad salad, please do better next year. |
| E0215 | honestly please add a board where people can post what they want to discuss would fix most of my days my whole team wants this | Honestly please add a board where people can post what they want to discuss. My whole team wants this |
| E0216 | Honestly the temperature in the main hall went from freezing to stuffy within an hour, pikc one would fix most of my days | The temperature in the main hall went from freezing to stuffy within an hour, pikc one. |
| E0221 | Third time asking: i came alone and left without meeting anyone, some structure would help | I came alone and left without meeting anyone, some structure would help. |
| E0222 | Would love feedback screech during the keynote start was rough | Feedback screech during the keynote start was rough. |
| E0224 | Would love please open regisrtation the night before like other conferences do I hit this every week | Please open regisrtation the night before like other conferences do. I hit this every week |
| E0233 | Can we get the chairs in track B were brutal for a full day? I hit this every week | The chairs in track B were brutal for a full day. I hit this every week |
| E0234 | feedback screech during the keynote start was rough is all I want we benchmark every tool against this | Feedback screech during the keynote start was rough. We benchmark every tool against this |
| E0242 | more breaks for chatting please, the schedule was wall to wall please, it is 2026 it came up in our retro again | More breaks for chatting please, the schedule was wall to wall. It came up in our retro again |
| E0257 | speed networking would have been useful, wandering the hall is not for everyone and I stop complaining | Speed networking would have been useful, wandering the hall is not for everyone. |
| E0265 | Would love pleas email the bdage QR code so we can skip the desk queue | Pleas email the bdage QR code so we can skip the desk queue. |
| E0275 | Third time asking: the car park was full by 9am, late arrivals drove around for half an hour | The car park was full by 9am, late arrivals drove around for half an hour. |
| E0278 | Honestly please arrange overflow parking, the venue lot held a fraction of the cars would fix most of my days my whole team wants this | Please arrange overflow parking, the venue lot held a fraction of the cars. My whole team wants this |
| E0280 | Honestly please open registration the night before like other conferences do would fix most of my days | Please open registration the night before like other conferences do. |
| E0286 | Can we get the food was cold by the time our session let out, stagger lunch with tracks? my whole team wants this | The food was cold by the time our session let out, stagger lunch with tracks. My whole team wants this |
| E0288 | the temperature in the main hall went from freezing to stuffy within an hour, pick one and I stop complaining | The temperature in the main hall went from freezing to stuffy within an hour, pick one. |
| E0293 | the food was cold by the time our session let out, stagger lunch with tracks would make my week | The food was cold by the time our session let out, stagger lunch with tracks. |
| E0307 | Third time asking: wifi password was buried in a slide, print it on the badge | Wifi password was buried in a slide, print it on the badge. |
| E0309 | Third time asking: more beginner friendly sessions please, some tracks assumed epxert knowledge | More beginner friendly sessions please, some tracks assumed epxert knowledge. |
| E0310 | please bring back the same keynote speaker next year, she was outstanding would make my week | Please bring back the same keynote speaker next year, she was outstanding. |
| E0313 | Adding registration staff were lovely but only two desks were open at 8am would help a lot | Registration staff were lovely but only two desks were open at 8am. |
| E0318 | Third time asking: recordings usually appear within a week for conferences like this, where are ours | Recordings usually appear within a week for conferences like this, where are ours? |
| E0320 | lightning talks were the highlight, add a second lightning session is all I want | Lightning talks were the highlight, add a second lightning session. |
| E0330 | Would love could not load the schedule site at all in the morning, wifi was dead | Could not load the schedule site at all in the morning, wifi was dead. |
| E0333 | Any chance of hall A was boiling in the afternoon, people were fanning themselves with programmes? | Hall A was boiling in the afternoon, people were fanning themselves with programmes. |
| E0348 | Can we get recordings usually appear within a week for conferences like this, where are ours? it came up in our retro again | Recordings usually appear within a week for conferences like this, where are ours? it came up in our retro again |
| E0349 | Can we get the directions sent said parking was on the west side, it was east? I would use it every single day | The directions sent said parking was on the west side, it was east. I would use it every single day |
| E0355 | the venue stairs were a bottleneck, please plan room changes better would make my week this blocks our rollout | The venue stairs were a bottleneck, please plan room changes better. This blocks our rollout |
| E0362 | check in took ofrever, the barcode scanner failed on half the badges please, it is 2026 three of my colleagues asked the same | Check in took ofrever, the barcode scanner failed on half the badges. Three of my colleagues asked the same |
| E0368 | Would love maybe stagger tracks by 15 minutes so people can hop between rooms | Maybe stagger tracks by 15 minutes so people can hop between rooms. |
| E0372 | Third time asking: speed was fine early, unusable after 10am, please add capacity it is the main gap for us | Speed was fine early, unusable after 10am, please add capacity. It is the main gap for us |
| E0384 | Third time asking: halal options were missing entirely, my colleague ate plain rice | Halal options were missing entirely, my colleague ate plain rice. |
| E0386 | Can we get talks were too long, 25 minutes would keep energy up? | Talks were too long, 25 minutes would keep energy up. |
| E0392 | Any chance of fruit and something not fried at breaks please, it was all pastries? | Fruit and something not fried at breaks please, it was all pastries. |
| E0393 | Any chance of the sponsor session felt like a sales pitch, mark it clearly or cut it? I hit this every week | The sponsor session felt like a sales pitch, mark it clearly or cut it. I hit this every week |
| E0395 | Third time asking: the mics in track C cut out constantly, questions from the floor were lost it came up in our retro again | The mics in track C cut out constantly, questions from the floor were lost. It came up in our retro again |
| E0399 | could not load the schedule site at all in the morning, wifi was dead and I stop complaining | Could not load the schedule site at all in the morning, wifi was dead. |

### what-people-ask-for/examples/feature_requests/feature_requests.csv

| Row id | Before | After |
|---|---|---|
| FR-0004 | Third time asking: i cannot migrate because import crashes, support said they would look into it weeks ago | I cannot migrate because import crashes, support said they would look into it weeks ago. |
| FR-0005 | Would love please build a native mobile app, the mobile web version keeps losing my taps | Please build a native mobile app, the mobile web version keeps losing my taps. |
| FR-0007 | Honestly i fly weekly for work and the app is useless on the lane, please add offline support would fix most of my days this blocks our rollout | I fly weekly for work and the app is useless on the lane, please add offline support. This blocks our rollout |
| FR-0009 | Third time asking: lease consider a dark theme, light mode in a dark office is rough | Lease consider a dark theme, light mode in a dark office is rough. |
| FR-0010 | Can we get i want an email digest each morning with what is due, that would help a lot? | I want an email digest each morning with what is due, that would help a lot. |
| FR-0013 | please add guest access, I collaborate with freelancers every month would make my week we benchmark every tool against this | Please add guest access, I collaborate with freelancers every month. We benchmark every tool against this |
| FR-0020 | Adding bulk re-tagging of cards, I renamed a client and now I redo 80 cards would help a lot | Bulk re-tagging of cards, I renamed a client and now I redo 80 cards. |
| FR-0021 | Can we get i work as a support tech at night, dark mode would save my eyes? it came up in our retro again | I work as a support tech at night, dark mode would save my eyes. It came up in our retro again |
| FR-0024 | show due dates on a month grid, that alone would help would make my week | Show due dates on a month grid, that alone would help. |
| FR-0025 | Can we get my internet cut out mid edit and I lost the task, offline mode would prevent this? I hit this every week | My internet cut out mid edit and I lost the task, offline mode would prevent this. I hit this every week |
| FR-0026 | labels with colours would help me separate work and personal tasks and I stop complaining my whole team wants this | Labels with colours would help me separate work and personal tasks. My whole team wants this |
| FR-0027 | sharing a read only view of a board with a link, please and I stop complaining | Sharing a read only view of a board with a link, please. |
| FR-0031 | Adding i need to export my tasks to CSV for a quarterly report, please add it would help a lot | I need to export my tasks to CSV for a quarterly report, please add it. |
| FR-0044 | Adding tag tasks with more than one tag, projects overlap and folders force me to choose would help a lot | Tag tasks with more than one tag, projects overlap and folders force me to choose. |
| FR-0045 | Honestly add reminder times not just dates, I schedule my day hour by hour would fix most of my days | Add reminder times not just dates, I schedule my day hour by hour. |
| FR-0051 | Honestly tag tasks with more than one tag, projects overlap and folders force me to choose woud fix most of my days three of my colleagues asked the same | Tag tasks with more than one tag, projects overlap and folders force me to choose. Three of my colleagues asked the same |
| FR-0055 | Any chance of let me rebind shortcuts, my left hand does not do ctrl? my whole team wants this | Let me rebind shortcuts, my left hand does not do ctrl. My whole team wants this |
| FR-0061 | Third time asking: i manage shift handovers and need tasks that repeat every shift, please add it | I manage shift handovers and need tasks that repeat every shift, please add it. |
| FR-0067 | Can we get block focus time on my calendar from a task, one click? | Block focus time on my calendar from a task, one click. |
| FR-0068 | Third time asking: scheduled exports by email every Monday would save me an hour | Scheduled exports by email every Monday would save me an hour. |
| FR-0071 | adding please support offline editing, customers in rural areas cannot use the app at all would help a lot we benchmark every tool against this | Please support offline editing, customers in rural areas cannot use the app at all. We benchmark every tool against this |
| FR-0077 | please support offline editing, customers in rural areas cannot use the app at all is all I want this blocks our rollout | Please support offline editing, customers in rural areas cannot use the app at all. This blocks our rollout |
| FR-0083 | google Calendar sync would be perfect, deadlines should live in my calendar would make my week | Google Calendar sync would be perfect, deadlines should live in my calendar. |
| FR-0086 | Any chance of please consider a dark theme, light mode in a dark office is rough? | Please consider a dark theme, light mode in a dark office is rough. |
| FR-0092 | apple Calendar support would help, I am on Mac and iPhone all day is all I want I would use it every single day | Apple Calendar support would help, I am on Mac and iPhone all day. I would use it every single day |
| FR-0093 | Would love dark mode is the one thing missing for me, everything else is great I would use it every single day | Dark mode is the one thing missing for me, everything else is great. I would use it every single day |
| FR-0099 | Can we get an iCal feed would be enough, I just want due dates in my calendar app? it is the main gap for us | An iCal feed would be enough, I just want due dates in my calendar app. It is the main gap for us |
| FR-0100 | Would love exporting to CSV is the reason I still keep a second tool around | Exporting to CSV is the reason I still keep a second tool around. |
| FR-0103 | please add guest access, I collaborate with freelancers every month please, it is 2026 | Please add guest access, I collaborate with freelancers every month. |
| FR-0110 | i want to assign tasks to colleagues and see their workload and I stop complaining this lbocks our rollout | I want to assign tasks to colleagues and see their workload. This lbocks our rollout |
| FR-0112 | Would love when is the Android app coming? I need my tasks on my phone three of my colleagues asked the same | When is the Android app coming? I need my tasks on my phone. Three of my colleagues asked the same |
| FR-0119 | Adding a printable shortcut cheat sheet in the docs would help a lot three of my colleagues asked the same | A printable shortcut cheat sheet in the docs. Three of my colleagues asked the same |
| FR-0132 | command palette like in VS Code would speed me up a lot please, it is 2026 my whole team wants this | Command palette like in VS Code would speed me up a lot. My whole team wants this |
| FR-0133 | per board permissions, interns should see fewer boards is all I want | Per board permissions, interns should see fewer boards. |
| FR-0134 | activity feed for a board so I can see what changed while I was away and I stop complaining | Activity feed for a board so I can see what changed while I was away. |
| FR-0135 | Honestly let a recurring task spawn the next one when I check it off would fix most of my days this blocks our rollout | Let a recurring task spawn the next one when I check it off. This blocks our rollout |
| FR-0141 | Would love i need a tagging system, folders are not enough for how I organise | I need a tagging system, folders are not enough for how I organise. |
| FR-0150 | night mode with true black for OLED phones please is all I want | Night mode with true black for OLED phones please. |
| FR-0152 | shortcut to open search with / like every other app would make my week this blocks our rollout | Shortcut to open search with / like every other app. This blocks our rollout |
| FR-0153 | Honetsly please add tags so I can filter my board by client would fix most of my days three of my colleagues asked the same | Honetsly please add tags so I can filter my board by client. Three of my colleagues asked the same |
| FR-0154 | Would love please integrate with Google Calendar, two way if possible I hit this every week | Please integrate with Google Calendar, two way if possible. I hit this every week |
| FR-0158 | coloured labels on cards like Trello has, please and I stop complaining my whole team wants this | Coloured labels on cards like Trello has, please. My whole team wants this |
| FR-0161 | please make search faster, it takes five seconds and often times out please, it is 2026 I would use it every single day | Please make search faster, it takes five seconds and often times out. I would use it every single day |
| FR-0164 | please consider a dark theme, light mode in a dark office is rough please, it is 2026 | Please consider a dark theme, light mode in a dark office is rough. |
| FR-0168 | location based reminders would be nice, remind me when I get to the office would make my week | Location based reminders would be nice, remind me when I get to the office. |
| FR-0175 | Honestly import from Notion crashes on my workspace, error code 500 would fix most of my days | Import from Notion crashes on my workspace, error code 500. |
| FR-0181 | bulk re-tagging of cards, I renamed a client and now I redo 80 cards and I stop complaining | Bulk re-tagging of cards, I renamed a client and now I redo 80 cards. |
| FR-0183 | please add calendar sync, I keep missing due dates because they are in a separate app would make my week we benchmark every tool against this | Please add calendar sync, I keep missing due dates because they are in a separate app. We benchmark every tool against this |
| FR-0186 | search should look inside task descriptions, not only titles, please fix this would make my week we benchmark every tool against this | Search should look inside task descriptions, not only titles, please fix this. We benchmark every tool against this |
| FR-0188 | Can we get import from Notion crashes on my workspace, error code 500? it is the main gap for us | Import from Notion crashes on my workspace, error code 500. It is the main gap for us |
| FR-0192 | a simple evvery Monday option for tasks would cover most of my needs please, it is 2026 | A simple evvery Monday option for tasks would cover most of my needs. |
| FR-0193 | search by person assigned would save my lead so much time is all I want | Search by person assigned would save my lead so much time. |
| FR-0194 | Honestly please notify me before a deadline, not on the day, a day before would be great would fix most of my days we benchmark every tool against this | Please notify me before a deadline, not on the day, a day before would be great. We benchmark every tool against this |
| FR-0203 | export with the comments included, my audit trail lives in the comments and I stop complaining | Export with the comments included, my audit trail lives in the comments. |
| FR-0205 | Third time asking: a simple every Monday option for tasks would cover most of my needs | A simple every Monday option for tasks would cover most of my needs. |
| FR-0206 | Honestly per board permissions, interns should see fewer boards would fix most of my days | Per board permissions, interns should see fewer boards. |
| FR-0209 | a phone app with offline support and notifications would replace three tools for me please, it is 2026 | A phone app with offline support and notifications would replace three tools for me. |
| FR-0215 | Would love pleae add due ddate reminders, I miss deadlines because nothing notifies me | Pleae add due ddate reminders, I miss deadlines because nothing notifies me. |
| FR-0230 | Can we get please add custom fields or tags, I track effort estimates in the title text right now? it came up in our retro again | Please add custom fields or tags, I track effort estimates in the title text right now. It came up in our retro again |
| FR-0233 | Can we get please let me press n to add a note without touching the mouse? I hit this every week | Please let me press n to add a note without touching the mouse. I hit this every week |
| FR-0242 | escalate overdue tasks to my email after three days is all I want | Escalate overdue tasks to my email after three days. |
| FR-0246 | Can we get slack reminders for due tsaks would fit our workflow? | Slack reminders for due tsaks would fit our workflow. |
| FR-0248 | Any chance of an iPhone app is the only reason I still pay for [rival tool]? | An iPhone app is the only reason I still pay for [rival tool]. |
| FR-0250 | the importer fails on boards with attachments, I tried four times is all I want | The importer fails on boards with attachments, I tried four times. |
| FR-0251 | Can we get night mode with true black for OLED phones please? this blocks our rollout | Night mode with true black for OLED phones please. This blocks our rollout |
| FR-0253 | Third time asking: a dark mode would be amazing, every other tool I use has one | A dark mode would be amazing, every other tool I use has one. |
| FR-0261 | Third time asking: recurring tasks would save me an hour a week, please | Recurring tasks would save me an hour a week, please. |
| FR-0266 | Honestly add task repetition with an end date, my team runs the same weekly audit would fix most of my days I hit this every week | Add task repetition with an end date, my team runs the same weekly audit. I hit this every week |
| FR-0269 | Can we get labels with colours would help me eparate work and personal tasks? | Labels with colours would help me eparate work and personal tasks. |
| FR-0271 | Any chance of bulk re-atgging of cards, I renamed a client and now I redo 80 cards? | Bulk re-atgging of cards, I renamed a client and now I redo 80 cards. |
| FR-0273 | Can we get let me rebind shortcuts, my left hand does not do ctrl? we benchmark every tool against this | Let me rebind shortcuts, my left hand does not do ctrl. We benchmark every tool against this |
| FR-0274 | wear OS or watch app for checking tasks off at the gym would make my week | Wear OS or watch app for checking tasks off at the gym. |
| FR-0275 | Any chance of please add filters combined with search, like search plus tag plus assignee? | Please add filters combined with search, like search plus tag plus assignee. |
| FR-0277 | Would love i want an email digest each morning with what is due, that would help a lot I hit this every week | I want an email digest each morning with what is due, that would help a lot. I hit this every week |
| FR-0278 | calDAV support please, I use a self hosted calendar would make my week | CalDAV support please, I use a self hosted calendar. |
| FR-0282 | Any chance of add the app to the Microsoft store for our managed laptops? three of my colleagues asked the same | Add the app to the Microsoft store for our managed laptops. Three of my colleagues asked the same |
| FR-0285 | Would love jSON export for our internal scripts please | JSON export for our internal scripts please. |
| FR-0286 | Any chance of activity feed for a board so I can see what changed while I was away? | Activity feed for a board so I can see what changed while I was away. |
| FR-0287 | Honestly a dark mode would be amazing, every other tool I use has one would fix most of my days it came up in our retro again | A dark mode would be amazing, every other tool I use has one. It came up in our retro again |
| FR-0291 | working offline then syncing when I am back, that is all I need is all I want | Working offline then syncing when I am back, that is all I need. |
| FR-0293 | block focus time on my calendar from a task, one click would make my week | Block focus time on my calendar from a task, one click. |
| FR-0294 | nested tags would help, client then project is all I want | Nested tags would help, client then project. |
| FR-0295 | being able to export to CSV would let me finally move my data into our BI tool and I stop complaining we benchmark every tool against this | Being able to export to CSV would let me finally move my data into our BI tool. We benchmark every tool against this |
| FR-0297 | Adding escalate overdue tasks to my email after three days would help a lot | Escalate overdue tasks to my email after three days. |
| FR-0301 | repeat options for tasks, daily weekly monthly, is the feature I miss most is all I want three of my colleagues asked the same | Repeat options for tasks, daily weekly monthly, is the feature I miss most. Three of my colleagues asked the same |
| FR-0303 | Third time asking: i need a tagging system, folders are not enough for how I organise this blocks our rollout | I need a tagging system, folders are not enough for how I organise. This blocks our rollout |
| FR-0314 | Honestly please add an export feature, CSV is fine, I just need the raw data out would fix most of my days | Please add an export feature, CSV is fine, I just need the raw data out. |
| FR-0316 | the web app on my phone is slow and the buttons are too small, a real app please is all I want | The web app on my phone is slow and the buttons are too small, a real app please. |
| FR-0319 | Adding sharing a read only view of a board with a link, please would heelp a lot | Sharing a read only view of a board with a link, please. |
| FR-0324 | importing my Trello board crashes the app at around 300 cards, please fix it would make my week | Importing my Trello board crashes the app at around 300 cards, please fix it. |
| FR-0325 | Would love a CSV export of a single board would be enough, please we benchmark every tool against this | A CSV export of a single board would be enough, please. We benchmark every tool against this |
| FR-0326 | please add dark mode, I use the app every evening and the white background hurts is all I want | Please add dark mode, I use the app every evening and the white background hurts. |
| FR-0331 | Honestly add CSV export so I can back up my work, I am scared of losing it all would fix most of my days I would use it every single day | Add CSV export so I can back up my work, I am scared of losing it all. I would use it every single day |
| FR-0334 | Adding add offline mode, my office wifi drops all day and I lose work would help a lot | Add offline mode, my office wifi drops all day and I lose work. |
| FR-0335 | Adding please add filters combined with search, like search plus tag plus assignee would help a lot I would use it every single day | Please add filters combined with search, like search plus tag plus assignee. I would use it every single day |
| FR-0340 | shortcut to open search with / like every other app and I stop complaining | Shortcut to open search with / like every other app. |
| FR-0341 | Honestly assign a task to two people, right now I duplicate it and it gets confusing would fix most of my days I hit this every week | Assign a task to two people, right now I duplicate it and it gets confusing. I hit this every week |
| FR-0343 | a high contrast mode would help my low vision users wouuld make my week | A high contrast mode would help my low vision users. |
| FR-0346 | Honestly jSON export for our internal scripts please would fix most of my days this blocks our rollout | JSON export for our internal scripts please. This blocks our rollout |
| FR-0347 | Any chance of i work as a support tech at night, dark mode would save my eyes? | I work as a support tech at night, dark mode would save my eyes. |
| FR-0351 | Adding night mode with true black for OLED phones please would help a lot | Night mode with true black for OLED phones please. |
| FR-0355 | search in comments too, decisions live in comment threads is all I want this blocks our rollout | Search in comments too, decisions live in comment threads. This blocks our rollout |
| FR-0364 | standup agenda items should repeat every workday automatically please, it is 2026 it is the main gap for us | Standup agenda items should repeat every workday automatically. It is the main gap for us |
| FR-0367 | Can we get can I invite a client to view one board without seeing the others? | Can I invite a client to view one board without seeing the others? |
| FR-0368 | Would love calendar view with sync to my phone calendar please | Calendar view with sync to my phone calendar please. |
| FR-0378 | Adding add CSV export so I can back up my work, I am scared of losing it all would help a lot this blocks our rollout | Add CSV export so I can back up my work, I am scared of losing it all. This blocks our rollout |
| FR-0384 | sharing a read only view of a board with a linkk, please would make my week | Sharing a read only view of a board with a linkk, please. |
| FR-0385 | can we get standup agenda items should repeat every workday automatically? I hit this every week | Standup agenda items should repeat every workday automatically. I hit this every week |
| FR-0386 | please add shared boards, my team plans in spreadsheets because the app is single player would make my week it is the main gap for us | Please add shared boards, my team plans in spreadsheets because the app is single player. It is the main gap for us |
| FR-0388 | Can we get add task repetition with an end date, my team runs the same weekly audit? | Add task repetition with an end date, my team runs the same weekly audit. |
| FR-0391 | add a theme setting, even a basic dark background helps and I stop complaining | Add a theme setting, even a basic dark background helps. |
| FR-0394 | Third time asking: cSV import please, I have my old tasks in a spreadsheet | CSV import please, I have my old tasks in a spreadsheet. |
| FR-0396 | our compliance team needs data exports, right now I have to screenshot everything would make my week my whole team wants this | Our compliance team needs data exports, right now I have to screenshot everything. My whole team wants this |
| FR-0399 | Would love let me rebind shortcuts, my left hand does not do ctrl | Let me rebind shortcuts, my left hand does not do ctrl. |
| FR-0400 | Can we get location based reminders would be nice, remind me when I get to the office? | Location based reminders would be nice, remind me when I get to the office. |
| FR-0402 | Honestly please fix the Trello import, it dies halfway through and leaves a half empty board would fix most of my days | Please fix the Trello import, it dies halfway through and leaves a half empty board. |
| FR-0404 | Any chance of per baord permissions, interns should see fewer boards? | Per baord permissions, interns should see fewer boards. |
| FR-0416 | Honestly please add dark mode, I use the app every evening and the white background hurts would fix most of my days | Please add dark mode, I use the app every evening and the white background hurts. |
| FR-0419 | Honestly i manage shift handovers and need tasks that repeatt every shift, please add it would fix most of my days | I manage shift handovers and need tasks that repeatt every shift, please add it. |
| FR-0421 | a CSV export of a single board would be enough, please please, it is 2026 we benchmark every tool against this | A CSV export of a single board would be enough, please. We benchmark every tool against this |
| FR-0424 | Would love please let me press n to add a note without touching the mouse we benchmark every tool against this | Please let me press n to add a note without touching the mouse. We benchmark every tool against this |
| FR-0426 | cache the last opened board for offline use, even read only please, it is 2026 | Cache the last opened board for offline use, even read only. |
| FR-0438 | i want to assign tasks to colleagues and see their workload is all I want it came up in our retro again | I want to assign tasks to colleagues and see their workload. It came up in our retro again |
| FR-0447 | Honestly please add due date reminders, I miss deadlines because nothing notifies me would fix most of my days | Please add due date reminders, I miss deadlines because nothing notifies me. |
| FR-0455 | please add filters combined with search, like search plus tag plus assignee please, it is 2026 | Please add filters combined with search, like search plus tag plus assignee. |
| FR-0460 | a high contrast mode would help my low vision users please, it is 2026 | A high contrast mode would help my low vision users. |
| FR-0461 | Third time asking: the web app on my phone is slow and the buttons are too small, a real app please | The web app on my phone is slow and the buttons are too small, a real app please. |
| FR-0462 | i wouuld pay extra for proper offline support, right now I keep paper notes please, it is 2026 my whole team wants htis | I wouuld pay extra for proper offline support, right now I keep paper notes. My whole team wants htis |
| FR-0463 | Third time asking: fuzzy search please, I never remember exact task names it is the main gap for us | Fuzzy search please, I never remember exact task names. It is the main gap for us |
| FR-0466 | dark theme for late night work sesions, my eyes are begging you would make my week | Dark theme for late night work sesions, my eyes are begging you. |
| FR-0467 | Honestly a simple every Monday option for tasks would cover most of my needs would fix most of my days | A simple every Monday option for tasks would cover most of my needs. |
| FR-0479 | Can we get cache the last opened board for offline use, even read only? | Cache the last opened board for offline use, even read only. |
| FR-0481 | Adding add labels and saved filters please, I look at the same client slice every dy would help a lot | Add labels and saved filters please, I look at the same client slice every dy. |
| FR-0482 | Adding my manager asks for a weekly summary and I am copy pasting by hand, CSV export please would help a lot | My manager asks for a weekly summary and I am copy pasting by hand, CSV export please. |
| FR-0488 | Any chance of weekly planning reminder on Monday mornings, my planner is a mess without it? three of my colleagues asked the same | Weekly planning reminder on Monday mornings, my planner is a mess without it. Three of my colleagues asked the same |
| FR-0493 | the web app on my phone is slow and the buttons are too small, a real app please would make my week we benchmark every tool against this | The web app on my phone is slow and the buttons are too small, a real app please. We benchmark every tool against this |
| FR-0494 | Would love add task repetition with an end date, my team runs the same weekly audit | Add task repetition with an end date, my team runs the same weekly audit. |
| FR-0499 | please add tags so I can filter my board by client is all I want | Please add tags so I can filter my board by client. |
| FR-0500 | the importer loses checklists inside cards, that is most of my data would make my week | The importer loses checklists inside cards, that is most of my data. |
| FR-0519 | recent searches dropdown would save me retyping please, it is 2026 | Recent searches dropdown would save me retyping. |
| FR-0521 | Any chance of can we please get a dark theme? The app is unusable at night without it? my whole team wants this | Can we please get a dark theme? The app is unusable at night without it. My whole team wants this |
| FR-0523 | Honestly push notifications on mobile matter more than a pretty app would fix most of my days | Push notifications on mobile matter more than a pretty app. |
| FR-0531 | Would love recent searches dropdown would save me retyping it came up in our retro again | Recent searches dropdown would save me retyping. It came up in our retro again |
| FR-0532 | labels with colours would help me separate work and personal tasks is all I want | Labels with colours would help me separate work and personal tasks. |
| FR-0535 | i fly weekly for work and the app is useless on the plane, please add offline support would make my eek it is the main gap for us | I fly weekly for work and the app is useless on the plane, please add offline support. It is the main gap for us |
| FR-0537 | third time asking: i need Outlook calendar integration, my whole company runs on Outlook it is the main gap for us | I need Outlook calendar integration, my whole company runs on Outlook. It is the main gap for us |
| FR-0538 | shortcut to open search with / like every other app is all I want we benchmark every tool against this | Shortcut to open search with / like every other app. We benchmark every tool against this |
| FR-0541 | the importer loses checklists inside cards, that is most of my data please, it is 2026 | The importer loses checklists inside cards, that is most of my data. |
| FR-0543 | offline queue for edits that sync later, I move through dead zones daily and I stop complaining this blocks our rollout | Offline queue for edits that sync later, I move through dead zones daily. This blocks our rollout |
| FR-0546 | Third time asking: better search please, half the time it inds nothing even when I know the task exists three of my colleagues asked the same | Better search please, half the time it inds nothing even when I know the task exists. Three of my colleagues asked the same |
| FR-0553 | Any chance of calDAV support please, I use a self hosted calendar? I would use it every single day | CalDAV support please, I use a self hosted calendar. I would use it every single day |
| FR-0556 | Would love offline queue for edits that sync later, I move through dead zones daily | Offline queue for edits that sync later, I move through dead zones daily. |
| FR-0558 | Any chance of my optician told me to cut screen glare, dark mode would help? | My optician told me to cut screen glare, dark mode would help. |
| FR-0561 | Honestly reminders with snooze please, I need to defer a reminder to tomorrow would fix most of my days it is the main gap for us | Reminders with snooze please, I need to defer a reminder to tomorrow. It is the main gap for us |
| FR-0562 | Honestly importing my Trello board crashes the app at around 300 cards, please fix it would fix most of my days | Importing my Trello board crashes the app at around 300 cards, please fix it. |
| FR-0563 | Honestly please add shared boards, my team plans in spreadsheets because the app is single player would fix most of my days | Please add shared boards, my team plans in spreadsheets because the app is single player. |
| FR-0566 | Adding please maek the app work offline, my commute has no signal for 40 mintues would help a lot | Please maek the app work offline, my commute has no signal for 40 mintues. |
| FR-0568 | Any chance of i fly weekly for work and the app is useless on the plane, please add offline support? my whole team wants this | I fly weekly for work and the app is useless on the plane, please add offline support. My whole team wants this |
| FR-0569 | Adding let me export a date range, not the whole history every time would help a lot | Let me export a date range, not the whole history every time. |
| FR-0570 | Any chance of the importer fails on boards with attachments, I tried four times? it came up in our retro again | The importer fails on boards with attachments, I tried four times. It came up in our retro again |
| FR-0572 | Any chance of i need Outlook calendar integration, my whole company runs on Outlook? | I need Outlook calendar integration, my whole company runs on Outlook. |
| FR-0573 | please add custom fields or tags, I track effort estimates in the title text righ now is all I want | Please add custom fields or tags, I track effort estimates in the title text righ now. |
| FR-0574 | Honestly i need to export my atsks to CSV for a quarterly report, please add it would fix most of my days | I need to export my atsks to CSV for a quarterly report, please add it. |
| FR-0576 | Adding importing my Trello board crashes the app at around 300 cards, please fix it would help a lot | Importing my Trello board crashes the app at around 300 cards, please fix it. |
| FR-0580 | Honestly i cannot migrate because import crashes, support said they would look into it weeks ago would fix most of my days | I cannot migrate because import crashes, support said they would look into it weeks ago. |
| FR-0585 | escalate overdue tasks to my email after three days and I tsop complaining it came up in our retro again | Escalate overdue tasks to my email after three days. It came up in our retro again |

### what-people-ask-for/examples/product_reviews/product_reviews.csv

| Row id | Before | After |
|---|---|---|
| R0001 | for the money I expected a sealed hopper and a better tray please, it is 2026 it came up in our retro again | For the money I expected a sealed hopper and a better tray. It came up in our retro again |
| R0008 | battery life is fine but the charging cable is proprietary, annoying would make my week I hit this every week | Battery life is fine but the charging cable is proprietary, annoying. I hit this every week |
| R0012 | great for pour over at medium settings, falls apart at the extremes please, it is 2026 it is the main gap for us | Great for pour over at medium settings, falls apart at the extremes. It is the main gap for us |
| R0014 | the box was fine but the burrs were loose in transit, rattling is all I want | The box was fine but the burrs were loose in transit, rattling. |
| R0016 | courier left it in the rain, box soaked, grinder sealed inside survived would make my week it is the main gap for us | Courier left it in the rain, box soaked, grinder sealed inside survived. It is the main gap for us |
| R0018 | three years in, daily use, only wear is the tray scratches is all I want | Three years in, daily use, only wear is the tray scratches. |
| R0027 | Honestly replacement arrived in two days, support gets credit for that would fix most of my days | Replacement arrived in two days, support gets credit for that. |
| R0041 | the grind is even enough for filter coffee, puck prep for espresso i a lottery and I stop complaining I would use it every single day | The grind is even enough for filter coffee, puck prep for espresso i a lottery. I would use it every single day |
| R0043 | Honestly value is real if you drink coffee daily, casual users should skip it would fix most of my days | Value is real if you drink coffee daily, casual users should skip it. |
| R0049 | at this price the burr set is the real story, same geometry as ggrinds twiec the cost and I stop complaining | At this price the burr set is the real story, same geometry as ggrinds twiec the cost. |
| R0052 | cheaper than cafe visits within two months for me, do the math please, it is 2026 this blocks our rollout | Cheaper than cafe visits within two months for me, do the math. This blocks our rollout |
| R0058 | Would love app shows a grind counter, mildly fun, totally unnecessary | App shows a grind counter, mildly fun, totally unnecessary. |
| R0059 | there are cheaper grinders that get you 90 percent of the way please, it is 2026 it came up in our retro again | There are cheaper grinders that get you 90 percent of the way. It came up in our retro again |
| R0066 | mess is contained compared to my old grinder, small win would make my week my whole team wants this | Mess is contained compared to my old grinder, small win. My whole team wants this |
| R0073 | Any chance of grounds cling to the clear bin and you cannot see the level? this blocks our rollout | Grounds cling to the clear bin and you cannot see the level. This blocks our rollout |
| R0083 | Would love sound is duller than my previous electric, still not quiet | Sound is duller than my previous electric, still not quiet. |
| R0084 | comes apart tool free which makes cleaning bearable please, it is 2026 | Comes apart tool free which makes cleaning bearable. |
| R0092 | static makes the grounds jump onto the scale and the counter please, it is 2026 | Static makes the grounds jump onto the scale and the counter. |
| R0094 | Can we get mornings are better but I still sift, the fines are heavy? | Mornings are better but I still sift, the fines are heavy. |
| R0095 | wakes the whole flat, grind before everyone wakes or accept the guilt is all I want three of my colleagues asked the same | Wakes the whole flat, grind before everyone wakes or accept the guilt. Three of my colleagues asked the same |
| R0096 | Any chance of at this price the burr set is the real story, same geometry as grinds twice the cost? | At this price the burr set is the real story, same geometry as grinds twice the cost. |
| R0104 | the grinder works fine without the app, ignore it and be happy would make my week | The grinder works fine without the app, ignore it and be happy. |
| R0113 | Would love there are cheaper grinders that get you 90 percent of the way | There are cheaper grinders that get you 90 percent of the way. |
| R0118 | Adding second unit also arrived with a ednted hopper, packing needs work would help a lot | Second unit also arrived with a ednted hopper, packing needs work. |
| R0122 | Would love rubber feet fell off within a month | Rubber feet fell off within a month. |
| R0124 | Any chance of the iptch is high and whiny, ear plugs at 7am? | The iptch is high and whiny, ear plugs at 7am. |
| R0125 | Honestly quieter after the first week, maybe the burrs seat in would fix most of my days | Quieter after the first week, maybe the burrs seat in. |
| R0126 | adding replacement unit ground better than the original, keep the tolerance complaints coming would help a lot | Replacement unit ground better than the original, keep the tolerance complaints coming. |
| R0128 | Adding mornings are better but I still sift, the fines aer heavy would help a lot I hit this every week | Mornings are better but I still sift, the fines aer heavy. I hit this every week |
| R0130 | one burr screw arrived loose, checked the manual, torque spec was listed, tightened it is alll I want | One burr screw arrived loose, checked the manual, torque spec was listed, tightened it. |
| R0131 | Adding  serial number plate was crooked, purely cosmetic would help a lot | Serial number plate was crooked, purely cosmetic. |
| R0134 | refilll funnel would be nice, pouring from a bag spills half the time would make my week my whole team wants this | Refilll funnel would be nice, pouring from a bag spills half the time. My whole team wants this |
| R0136 | battery indicator is a lie, shows two bars then dies mid grind and I stop complaining | Battery indicator is a lie, shows two bars then dies mid grind. |
| R0156 | quieter after the first week, mmaybe the burrs seat in is all I want I hit this every week | Quieter after the first week, mmaybe the burrs seat in. I hit this every week |
| R0157 | Third time asking: the step up in cup quality from a blade grinder is enormous fo the money | The step up in cup quality from a blade grinder is enormous fo the money. |
| R0161 | the crevice under the burr collects oils, use a grindz tablet monthly and I stop complainingg | The crevice under the burr collects oils, use a grindz tablet monthly. |
| R0162 | Adding hopper lid does not seal, beans go stale if you store them in it would help a lot | Hopper lid does not seal, beans go stale if you store them in it. |
| R0164 | Any chance of the grinder works fine without the app, ignore it and be happy? I hit this every week | The grinder works fine without the app, ignore it and be happy. I hit this every week |
| R0169 | the hopper exit chute traps one bean every time, shake it loose please, it is 2026 | The hopper exit chute traps one bean every time, shake it loose. |
| R0173 | iin winter the static is terrible, try the RDT trick, a drop of water on the beans would make my week | Iin winter the static is terrible, try the RDT trick, a drop of water on the beans. |
| R0175 | Adding espresso range is good but the steps between settings are too coarse to dial in would help a lot three of my colleagues asked the same | Espresso range is good but the steps between settings are too coarse to dial in. Three of my colleagues asked the same |
| R0183 | Any chance of espresso range is good but the steps between ssettings are too coarse to dial in? | Espresso range is good but the steps between ssettings are too coarse to dial in. |
| R0185 | Adding a full charge does about 30 grinds, more than enough for me would help a lot | A full charge does about 30 grinds, more than enough for me. |
| R0198 | Any chance of retention is low which I like, what comes out is what went in? | Retention is low which I like, what comes out is what went in. |
| R0199 | Honestly metal body is a fingerprint magnet but feels sturdy would fix most of my days | Metal body is a fingerprint magnet but feels sturdy. |
| R0200 | Honestly delivered a day early and undamaged, no complaints here would fix most of my days it is the main gap for us | Delivered a day early and undamaged, no complaints here. It is the main gap for us |
| R0209 | Third time asking: the crevice under the burr collects oils, use a grindz tablet monthly | The crevice under the burr collects oils, use a grindz tablet monthly. |
| R0210 | comes apart tool free which makes cleaning bearable would make my week | Comes apart tool free which makes cleaning bearable. |
| R0216 | Third time asking: firmware update over the app failed halfway, had to factory reset it came up in our retro again | Firmware update over the app failed halfway, had to factory reset. It came up in our retro again |
| R0217 | Any chance of static makes the grounds jump ono the scale and the counter? | Static makes the grounds jump ono the scale and the counter. |
| R0227 | wipe the chute with a dry cloth and the static calms down for a few days please, it is 2026 this blocks our rollout | Wipe the chute with a dry cloth and the static calms down for a few days. This blocks our rollout |
| R0234 | Would love the price went up 30 dollars since I bought mine, glad I got in early | The price went up 30 dollars since I bought mine, glad I got in early. |
| R0244 | hopper lid does not seal, beans go stale if you store them in it please, it is 2026 it came up in our retro again | Hopper lid does not seal, beans go stale if you store them in it. It came up in our retro again |
| R0245 | Third time asking: battery life is fine but the charging cable is proprietary, annoying | Battery life is fine but the charging cable is proprietary, annoying. |
| R0246 | price is fair for the burrs, the rest of the machine is basic is all I want | Price is fair for the burrs, the rest of the machine is basic. |

### what-people-ask-for/examples/support_tickets/support_tickets.csv

| Row id | Before | After |
|---|---|---|
| T00004 | resend button does nothing, clicked five times over an hour and I stop complaining | Resend button does nothing, clicked five times over an hour. |
| T00006 | Can we get mentions do not notify me, I only find them when I open the app? it is the main gap for us | Mentions do not notify me, I only find them when I open the app. It is the main gap for us |
| T00010 | Any chance of the export zip downloads as a 0 byte file, tried twice? this blocks our rollout | The export zip downloads as a 0 byte file, tried twice. This blocks our rollout |
| T00011 | Any chance of aPI responses are suddenly slow, 4 seconds for a list call? | API responses are suddenly slow, 4 seconds for a list call. |
| T00017 | Any chance of where is the recycle bin? I deleted a board by accident? we benchmark every tool against this | Where is the recycle bin? I deleted a board by accident. We benchmark every tool against this |
| T00018 | Would love webhook payload changed shape without a version bump | Webhook payload changed shape without a version bump. |
| T00026 | login fails with 'invalid credentials' but I can log into the forum with the same password and I stop complaining | Login fails with 'invalid credentials' but I can log into the forum with the same password. |
| T00031 | Would love aPI responses are suddenly slow, 4 seconds for a list call | API responses are suddenly slow, 4 seconds for a list call. |
| T00035 | Honestly i want to move 2FA to a hardware key, how would fix most of my days | I want to move 2FA to a hardware key, how? |
| T00037 | Can we get one board refuses to sync, others are fine, since yesterday? three of my colleagues asked the same | One board refuses to sync, others are fine, since yesterday. Three of my colleagues asked the same |
| T00040 | my account seems locked after the office IP changed, is there an allowlist please, itt is 2026 | My account seems locked after the office IP changed, is there an allowlist? |
| T00043 | Adding we are a team of six and half of us see stale board would help a lot | We are a team of six and half of us see stale board. |
| T00047 | Honestly password reset link opens a blank page would fix omst of my days it came up in our retro again | Password reset link opens a blank page. It came up in our retro again |
| T00050 | Adding password reset link opens a blank page would help a lot | Password reset link opens a blank page. |
| T00055 | Any chance of i switched phones and the authenticator codes are wrong noww? | I switched phones and the authenticator codes are wrong noww. |
| T00065 | Can we get notification sound plays with no visible notification on desktop? | Notification sound plays with no visible notification on desktop. |
| T00066 | Would love please let us tag other teams in comments | Please let us tag other teams in comments. |
| T00070 | the reset email goes to spam for our whole domain, sender reputation issue please, it is 2026 | The reset email goes to spam for our whole domain, sender reputation issue? |
| T00073 | Third time asking: after the update I cannot log in at all, it loops back to the login screen | After the update I cannot log in at all, it loops back to the login screen. |
| T00077 | can I change the workspace timezone? Deadlines show one hour off is all I want | Can I change the workspace timezone? Deadlines show one hour off. |
| T00081 | i stopped getting any emails from you since the 14th and I stop complaining it came up in our retro again | I stopped getting any emails from you since the 14th. It came up in our retro again |
| T00089 | my card was declined but the charge shows pending, now twice is all I want I would use it every single day | My card was declined but the charge shows pending, now twice. I would use it every single day |
| T00091 | Would love how do I set business hours for the shared inbox | How do I set business hours for the shared inbox? |
| T00101 | Can we get i want to move 2FA to a hardware key, how? | I want to move 2FA to a hardware key, how? |
| T00112 | Third time asking: my account seems locked after the office IP changed, is there an allowlist I hit this every week | My account seems locked after the office IP changed, is there an allowlist? I hit this every week |
| T00116 | Any chance of please batch notification emails, I get 40 a day? it came up in our retro again | Please batch notification emails, I get 40 a day. It came up in our retro again |
| T00118 | Adding resend button does nothing, clicked five times over an hour would help a ot I would use it every single day | Resend button does nothing, clicked five times over an hour. I would use it every single day |
| T00119 | 2FA setup QR code never scas, tried two apps is all I want | 2FA setup QR code never scas, tried two apps. |
| T00126 | Can we get i cannot log in with Google SSO since our admin changed the domain? | I cannot log in with Google SSO since our admin changed the domain. |
| T00129 | after the 4.2 update the app crashes in settings, sync section would make my week I would use it every single day | After the 4.2 update the app crashes in settings, sync section. I would use it every single day |
| T00131 | Can we get reset flow says my mail is not found, but I am logged in on mobile? | Reset flow says my mail is not found, but I am logged in on mobile. |
| T00145 | slack notifications from your integration are delayed by hours please, it is 2026 it is the main gap for us | Slack notifications from your integration are delayed by hours. It is the main gap for us |
| T00149 | Honestly please add recurring cards, we recreate the samme weekly checklist would fix most of my days | Please add recurring cards, we recreate the samme weekly checklist. |
| T00153 | Adding the JSON export has dates in unix time, spreadsheets choke on them would help a lot this blocks our rollout | The JSON export has dates in unix time, spreadsheets choke on them. This blocks our rollout |
| T00161 | oAuth token refresh fails with a cryptic error is all I want | OAuth token refresh fails with a cryptic error. |
| T00166 | Any chance of please add an API endpoint for exports, the manual download is not automatabble? | Please add an API endpoint for exports, the manual download is not automatabble. |
| T00167 | Can we get how do I add a second admin to our workspace? | How do I add a second admin to our workspace? |
| T00172 | the 2FA prompt appears every login even on trusted devices and I stop complaining we benchmark every tool against this | The 2FA prompt appears every login even on trusted devices. We benchmark every tool against this |
| T00177 | Would love sync cconflicts create duplicate cards, we now have three copies of one task | Sync cconflicts create duplicate cards, we now have three copies of one task. |
| T00180 | Adding app freezes when the keyboard opens in the comment box, iPhone 15 would help a lot it came up in our retro again | App freezes when the keyboard opens in the comment box, iPhone 15. It came up in our retro again |
| T00182 | after the update I cannot log in at all, it loops back to the login screen is all I want my whole team wants this | After the update I cannot log in at all, it loops back to the login screen. My whole team wants this |
| T00185 | i switched phones and the authenticator codes are wrong now and I stop complaining | I switched phones and the authenticator codes are wrong now. |
| T00187 | i cancelled my subscription but was still charged, please refund would make my week | I cancelled my subscription but was still charged, please refund. |
| T00196 | my card was declined but the charge shows pending, now twice and I stop complaining | My card was declined but the charge shows pending, now twice. |
| T00198 | Can we get we were charged in USD but our account is set to EUR? | We were charged in USD but our account is set to EUR. |
| T00205 | Would love the reset email goes to spam for our whole domain, sender reputation issue | The reset email goes to spam for our whole domain, sender reputation issue? |
| T00210 | iPad app crashes when rotating to landscape is all I want I hit this every week | IPad app crashes when rotating to landscape. I hit this every week |
| T00214 | Can we get the API returned a 500 for two hours last night, no status page note? I would use it every single day | The API returned a 500 for two hours last night, no status page note. I would use it every single day |
| T00217 | honestly uor integration hit rate limits with 3 requests per second, docs said 10 would fix most of my days three of my colleagues asked the same | Honestly uor integration hit rate limits with 3 requests per second, docs said 10. Three of my colleagues asked the same |
| T00223 | Adding mentions do not notify me, I only find them when I open the app would help a lot | Mentions do not notify me, I only find them when I open the app. |
| T00231 | please add recurring cards, we recreate the same weekly checklist is alll I want | Please add recurring cards, we recreate the same weekly checklist. |
| T00235 | Honestly the reset page is blocked by our corporate proxy, certificate error would fix most of my days we benchmark every tool against this | The reset page is blocked by our corporate proxy, certificate error. We benchmark every tool against this |
| T00240 | i never received the reset email, checked spam and filters please, it is 2026 | I never received the reset email, checked spam and filters. |
| T00241 | Can we get how do I set business hours for the shared inbox? | How do I set business hours for the shared inbox? |
| T00243 | login page hangs on thhe spinner, tried three browser please, it is 2026 | Login page hangs on thhe spinner, tried three browser. |
| T00252 | i need a receipt for a purchase from March, portal has no history is all I want it came up in our retro again | I need a receipt for a purchase from March, portal has no history. It came up in our retro again |
| T00253 | one board refuses to sync, others are fine, since yesterday please, it is 2026 | One board refuses to sync, others are fine, since yesterday. |
| T00255 | Adding the team plan charged me for 12 seats but we removed 4 last month would help a lot | The team plan charged me for 12 seats but we removed 4 last month. |
| T00263 | Adding i never received the reset email, checked spam and filters would help a lot my whole team wants this | I never received the reset email, checked spam and filters. My whole team wants this |
| T00266 | Adding i need a receipt for a purchase from March, portall has no history would help a lot my whole team wants this | I need a receipt for a purchase from March, portall has no history. My whole team wants this |
| T00269 | login works on desktop but not on mobile web please, it is 2026 | Login works on desktop but not on mobile web. |
| T00272 | Honestly where do I find the audit log you mentioned in the changelog would fix most of my days I hit this every week | Where do I find the audit log you mentioned in the changelog? I hit this every week |

## 3. Re-running the recipe after the change

`piles.py` was re-run on every what-people-ask-for example, before the change
and after, on the same machine, same model, CPU. Numbers are pasted from the
`--json` output.

| Example | rows read | exact dupes dropped | grouped | groups | said-again clusters |
|---|---|---|---|---|---|
| feature_requests | 585 / 585 | 2 / 24 | 583 / 561 | 18 / 13 | 130 / 131 |
| product_reviews | 248 / 248 | 0 / 2 | 248 / 246 | 14 / 13 | 48 / 54 |
| support_tickets | 273 / 273 | 0 / 6 | 273 / 267 | 12 / 10 | 62 / 62 |
| event_feedback | 403 / 403 | 0 / 7 | 403 / 396 | 19 / 11 | 85 / 84 |
| talk_proposals | 301 / 301 | 2 / 2 | 299 / 299 | 10 / 10 | 52 / 52 |

Before / after, read as "before / after". The drop in grouped rows comes from
fixed rows that now exactly duplicate another row; `piles.py` drops exact
duplicates before grouping. Group labels shift for the same reason.
`talk_proposals.csv` only had its email domains changed, so its numbers stay.

The two cookbooks with README numbers (`what-changed`, `show-me-where`) use
different sample files that were not touched, so no README number changed.
The what-people-ask-for folders have no README. The executed outputs stored in
`walkthrough.ipynb` predate this change: they were real when the notebook ran,
and the notebook was not re-executed or edited.

## 4. report.html and groups.csv

The committed `report.html` and `groups.csv` files in the five what-people-ask-for
example folders were regenerated from the fixed CSVs so they match the data.

