整个记忆系统，或许可以作为一个 cli ? , 但是只作为cli 的话不好处理 上下文
做一个数据库访问的cli , 有会话状态的？ 还是先了解下现有cli的能力吧
终端操作的 cli 
上下文管理，终端数据压缩
自动多窗口任务
长任务测试

基于文件的记忆系统
一些特定工作的skill
  arthas 类替换
  请求接口并查看 arthas 日志
  发布新pod
  查看一个pod是否启动成功
	
-- 探索命令行的集成，如 dbcli 代替mcp 
-- skill 可区分为需要独立agent和不需要
-- 优化，明确配置方式
会话和对话id

不论什么功能，不要光想，有想的功夫都做出来了，先做出来再说

duckdb 作为skill 集成，实现数据拉取和分析
  做一duckdb cli ，发现官方有cli
  官方 cli 是系统级工具，不够“绿色版”，方便skill 安装
  pyhton 代码中用 duckdb 可以做 ETL ,但这个是要 agent 生成代码，执行效率不高

agent 到底，本质上，提供的是什么能力？

可以在 exec bash tool 中增加环境变量的功能， 就是如果命令中带有环境变量，这个环境变量就是系统环境变量的写法，但在tool这一层灰先解析并替换一遍，用的是tool从当前会话上下文中拿到的数据
思考：如果一个skill的运行依赖另一个skill ,怎么处理？在 agent 模式下，这种 inject 模式的skill ，是不是应该允许skill agent 以inject 模式来使用其他skill

记忆文件移动到 .termbot 下
支持运行 skill 目录下脚本
























