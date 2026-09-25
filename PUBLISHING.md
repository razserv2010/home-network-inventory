# פרסום עצמי ב־GitHub

אפשר להעלות את המאגר בלי לתת לאיש אחר גישה לחשבון.

1. היכנס לחשבון GitHub שלך וצור מאגר חדש בשם `home-network-inventory` עם נראות **Public**. השאר את האפשרויות להוספת README, רישיון ו־`.gitignore` לא מסומנות: הקבצים כבר כלולים בחבילה.
2. חלץ את ZIP המקור למחשב. בעמוד המאגר החדש בחר **uploading an existing file** או **Add file → Upload files** והעלה את קובצי הפרויקט ואת התיקיות `templates` ו־`static`. ודא שגם הקובץ `.gitignore` נכלל. אם המאגר כבר קיים, העלה את הקבצים המעודכנים לתיקיות המתאימות באותו מבנה.
3. לחץ **Commit changes**. בדף הראשי אמורים להופיע `README.md`, `LICENSE`, `app.py`, `install.sh`, `UPGRADE`, `requirements.txt`, `templates/index.html` ותיקיית `static` עם הסמל וה־manifest.
4. פתח את `README.md` באתר וודא שפקודת השכפול מפנה לכתובת `https://github.com/razserv2010/home-network-inventory.git`.

לפני ההעלאה ודא שתיקיות `data` ו־`.venv` וקובצי `.sqlite3` אינם נכללים. אין להעלות גיבויי JSON שמכילים כתובות IP או MAC אמיתיות. חבילת המקור שסופקה מכילה רק קוד ותיעוד.

לאחר הפרסום, אפשר להוסיף בעמוד המאגר תיאור קצר: **Hebrew self-hosted home network inventory with device labels, Ping status, filters, and JSON backup.**

## פרסום גרסה שמפעילה הודעת עדכון

הודעת עדכון בממשק מופיעה רק אחרי פרסום **GitHub Release** חדש, ולא אחרי כל commit. אחרי שהעלית ובדקת את הקבצים, היכנס בעמוד המאגר ל־**Releases → Draft a new release**, צור תגית חדשה כגון `v1.0.0` על הענף `main`, הוסף תיאור קצר ולחץ **Publish release**. אל תסמן את הגרסה כ־Pre-release אם ברצונך שתופיע למשתמשים כהעדכון האחרון. בפעם הבאה שתרצה לפרסם גרסה חדשה, העלה את השינויים ובדוק אותם תחילה, ואז פרסם Release עם תגית חדשה כגון `v1.1.0`.

משתמש שהתקין מהמאגר יקבל הודעה כאשר הגרסה החדשה אינה כלולה בהתקנה שלו. כדי לעדכן, עליו להיכנס לתיקיית הפרויקט ב־SSH ולהריץ `bash UPGRADE`. מי שהתקין לפני שהקובץ `UPGRADE` נוסף למאגר צריך לבצע פעם אחת `git pull` ואז `bash UPGRADE`.
