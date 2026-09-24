# פרסום עצמי ב־GitHub

אפשר להעלות את המאגר בלי לתת לאיש אחר גישה לחשבון.

1. היכנס לחשבון GitHub שלך וצור מאגר חדש בשם `home-network-inventory` עם נראות **Public**. השאר את האפשרויות להוספת README, רישיון ו־`.gitignore` לא מסומנות: הקבצים כבר כלולים בחבילה.
2. חלץ את ZIP המקור למחשב. בעמוד המאגר החדש בחר **uploading an existing file** או **Add file → Upload files** והעלה את קובצי הפרויקט ואת תיקיית `templates`. ודא שגם הקובץ `.gitignore` נכלל.
3. לחץ **Commit changes**. בדף הראשי אמורים להופיע `README.md`, `LICENSE`, `app.py`, `install.sh`, `requirements.txt` ו־`templates/index.html`.
4. פתח את `README.md` באתר וודא שפקודת השכפול מפנה לכתובת `https://github.com/razserv2010/home-network-inventory.git`.

לפני ההעלאה ודא שתיקיות `data` ו־`.venv` וקובצי `.sqlite3` אינם נכללים. אין להעלות גיבויי JSON שמכילים כתובות IP או MAC אמיתיות. חבילת המקור שסופקה מכילה רק קוד ותיעוד.

לאחר הפרסום, אפשר להוסיף בעמוד המאגר תיאור קצר: **Hebrew self-hosted home network inventory with device labels, Ping status, filters, and JSON backup.**
