import sqlite3

# 操作的数据库名为weird_prompt.db，数据库名称固定不变
# 这个节点可以新建表（自定义表命），查询表（下拉菜单选择表）在comfyui web前端

# 表定义
#CREATE TABLE MYTABLE(
#   ID INTEGER PRIMARY KEY,
#   prompt_name  TEXT,
#   prompt_text  TEXT,
#   prompt_lora  TEXT,
#   prompt_trigger  TEXT
#);

# 这个节点可以增删改查表中的非ID的4个键，在comfyui web前端
# 四个键都可以输出

# 尽量复用comfyui原始控件