# Bouncer

A Discord moderation bot to keep track of the bad eggs | Бот для модерації Discord серверів та стеження за неслухняними дупцями

Творець - daniellatlumcah, серпень 2022-2023
<br>Written by daniellatlumcah, August 2022-2023

[Першотвір](https://github.com/aquova/bouncer/) - aquova, 2018-2023
<br>[Original](https://github.com/aquova/bouncer/) by aquova, et. al, 2018-2023

https://discord.gg/t4VWq3mGxa

## Огляд

Оригінальна версія цього боту написана для допомоги в модерації на Discord сервері SDV, ця ж - для українського серверу SDV, але він може бути легко використаний на будь-якому сервері, який вимагає більш просунутої реєстрації модерації.

Хостинг цього бота буде приватним. Бот створений саме для модерації серверу SDV Україна, тому цей резиторій тут більше як приклад, ніж ресурс для безпосереднього використання іншими.

## Характеристики

Бот має низку функцій модерації:

- Ведення журналу попереджень користувача
    - Модератори можуть реєструвати попередження користувачів поряд з пояснювальним повідомленням.
    - Попередження зберігаються як в каналі Discord, вказаному в файлі `config.json`, так і в локальній базі даних.
    - На додаток до попереджень можна відзначити блокування (тобто бани), вигнання та розблокування.
- Зберігання зауважень модераторів
    - Зауваження про користувачів зберігаються в приватному порядку, для подальшого перегляду модераторами.
- Пошук користувачів
    - Пошук у базі даних можна здійснювати за ідентифікатором користувача, ім'ям користувача або за допомогою пінґу. Після цього бот опублікує будь-які помічені порушення, а також їхню дату та збережене повідомлення.
- Вилучення
    - Всі помиляються. Журнали окремих користувачів можна редагувати і видаляти.
- Пересилання ПП
    - Приватні повідомлення, надіслані боту, будуть автоматично перенаправлені до каналу, вказаний в `config.json`.
    - Модератори також можуть відповідати користувачеві через бота, що дозволяє спільно переглядати прямі повідомлення.
    - ПП від порушників можуть бути заблоковані та розблоковані за бажанням.
- Автовідповідач
    - Для того, щоб випадково не пропустити повідомлення, можна переглянути список користувачів, які очікують на відповідь.
    - Список автоматично зменшується після того, як повідомлення стає занадто старим, або якщо на нього відповіли.
- Листування з користувачами через ПП
     - Після блокування або попередження є можливість надіслати користувачеві ПП. Це можна вимкнути у файлі `config.json`.
- Візуалізація статистичних даних
     - Можна формувати статистику активності модераторів, а саме: скільки попереджень/банів було зроблено за місяць та скільки всього попереджень/банів було створено кожним модератором.
- Системні журнали
     - Також бот буде моніторити всі канали та повідомляти про загальносерверні зміни в користувачах.
     - До них відносяться зміна ніків, приєднання, вихід, вигнання, бан, приєднання/вихід з ГК, а також ведення журналу всіх видалених і змінених повідомлень.
- Налагодження
     - Копія бота може бути вказана як налагоджувальна.
     - Копії, що не налагоджуються, ігноруватимуть команди від власника, коли налагодження ввімкнено, дозволяючи розробку, поки інші копії залишаються в режимі реального часу на сервері.
- Список відстеження
     - Потенційно проблемні користувачі можуть бути додані до 'списку відстеження', де всі їхні повідомлення розміщуються для зручного перегляду.
     - Це дозволяє швидко побачити, чи продовжує можливий троль публікувати повідомлення, замість того, щоб покладатися на пошук від Discord.

Також є команда `$help`, яка видасть список всіх раніше перелічених команд.

Для більшої безпеки бот відповідає на команди команди тільки в певних каналах, а приймає команди тільки від користувачів з певними ролями. Вони можуть бути вказані разом з іншими параметрами у файлі `config.json`, якого в цьому репозиторії нема зі зрозумілих міркувань безпеки.
