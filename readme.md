# Without proxy
Создайте или отредактируйте запускаемый файл start.bat.
Вместо login и password укажите действующие логин и пароль
```
python load.py -l login -p password
```
Запустите start.bat из консоли.
Программа запустит браузер и попросит выбрать нужный разде и нажать Enter в консоли после того как раздел будет выбран в браузере.

# With proxy
Создайте или отредактируйте запускаемый файл start.bat.
Вместо login и password укажите действующие логин и пароль
Вместо proxy_host и proxy_port укажите адрес и порт прокси сервера. 
```
python load.py -l login -p password -x proxy_host:proxy_port
```
Если вы используете Tor запустите Tor Browser.   
По умолчанию Tor Browser создает socks proxy  по адресу 127.0.0.1:9150
```
python load.py -l login -p password -x 127.0.0.1:9150
```