# bupt hotel management system
波普特廉价酒店管理系统，北京邮电大学2023年秋季-软件工程-课程设计。

> 用心做好一件事。

> 在软件开发的生命周期中，软件维护才是耗时最多的环节。

这虽然是2023年秋季的软件工程课程设计，但是至今仍在维护，我看到了有很多后人star这个仓库，说明它还在发挥它的作用。维护这个仓库，做好一份代码，是一件很有意义的事情。

# 分支说明

您目前正在：**backend Golang分支**

# News

+ [2024-09-14] 计划重写Python后端，舍弃旧的Flask + pymysql框架，选用FastAPI + Asyncio + aiosqlite.
+ [2024-04-11] 新增golang后端，对协程提供更好的支持。
+ [2023-12-17] 完成Python后端的搭建，完成基于Vue的前端的初步搭建。

# 技术栈详情
+ Vue3 (axios, element-plus)
+ Python backend: Flask + pymysql
+ Golang backend: Gin + GORM

# 任务分析

波普特酒店管理系统这个任务，本质上是一个IO bound的系统，也就是说可能系统的bottleneck大多数都在IO上面（与数据库进行IO）.既然是一个IO Bound的task，一门支持协程的语言是很有必要的。

协程本质上的思想，就是在一个coroutine挂起的时候，去执行另一个协程。比如：

+ A协程遇到了网络请求IO，或者数据库IO（等待其他人完成工作，自己只是在等待）
+ 这个时候，我们会选择把A协程挂起。因为这是无意义的等待，这个等待时间我们完全可以执行其他事情。
+ 挂起A协程，执行B协程
+ 等A协程完成了IO，我们再执行A协程后续的代码段

这就是协程最基本的思想，通过挂起IO等待中的协程，计算其他协程的任务，以提高整个系统的并发量，从而提高请求的吞吐量。

---


__旧版Python后端存在的问题__

后端与数据库的交互部分时不时会崩掉，原因未知，但是大多数时候是能跑的。（不清楚到底是网络的问题还是电脑与MySQL Connection的问题还是代码的问题，不过从报错信息上来看似乎是使用连接的方式有问题，后人可以完善一下连接池的处理）




# 如何启动

## 1. Python backend

**请严格按照：启动后端-启动前端-启动checkin的顺序执行！！！！！**

### 1.1 __后端启动：__

后端部分的启动较为复杂，在启动之前，你需要先配置好你的数据库。



__step 1: 修改账户与密码以适应你的配置__

首先，你需要记住你的数据库连接的账户和密码。

在这份代码中，本人的配置是用户名为root，密码为1234，这两个信息你需要在`backend/master.py`的：

+ DATABASE_USER_NAME
+ DATABASE_USER_PASSWORD

更改为你自己的。



__step 2: 创建一个空数据库db（或者叫schema）__

```sql
CREATE DATABASE backend;
```

这个空数据库的名字就叫`backend`。创建好了即可。



__step 3: 启动server__

```bash
cd backend
python server.py
```

注意：

1. 启动之后，会自动对数据库进行一系列初始化，无需担心数据库的问题。
2. 在启动过程中，遇到什么缺的包直接`pip install`即可。



### 1.2 __前端启动：__

**注意：在启动前端之前，必须先启动后端！！！**

```bash
cd frontend
npm run dev
```

**注意：** 你需要安装一些packages，这个可以通过`node.js`安装，遇到缺失的直接`npm install`就行。



### 1.3 进行checkin

为了方便，我们每次都是通过一份脚本进行checkin的，而不是手动去前端那里戳戳戳

启动checkin脚本的指令：

```bash
cd tests
python checkin.py
```

注意，一定要在启动后端之后，再执行checkin脚本。



### 1.4 测试脚本

为了验证我们的系统到底怎么样，我们有一份测试脚本。

根据老师给出的样例，对服务器进行测试

脚本启动指令:

```bash
cd tests
python SE-TEST.py
```

之后会生成一份`result.xlsx`文件作为输出结果（如果运行顺利的话）



## 2. Golang backend

非常简单，仅仅需要你安装了golang环境即可。



```bash
git clone https://github.com/SamuraiBUPT/bupt-hotel-management
cd bupt-hotel-management

cd backend_go/src
bash launch.sh
```

之后会自动创建数据库、启动server。



# 写在后面

前端部分有很多没有完成的，因为是助教验收，所以三两下糊弄过去就完事。

+ 登陆页面（为了联调，登陆改为前端自己的事情，但是实际上应该是与后端联合的，那段代码被我注释掉了，取消注释应该就可以运行）
+ 各种面板
  + 前台面板：有一些结账逻辑没有完善、比如说checkout之后，房间的清空之类的。
  + 管理员面板：至今unfinished，我也不想管了
  + 经理面板：查看日报、周报的功能，这里应该用前端狠狠渲染出一份很好看的图表的，但是我们完全没做，甚至那份前端的路由都没创建，后端也没有对应的接口，可以说这部分几乎为0.
+ 各种美化工作
  + 我的前端界面在各种八仙过海一般的前端界面中，勉强算是能看的，归功于`element-plus`提供的组件库，让我不用太考虑布局样式之类的，也能勉强看得顺眼。
  + 但是实际上如果肯花时间的话，这部分的美化工作一定是可以做的很好的。

这一份作业真正开工到完工的时间也就两周。大家可以作为一份base，在这个基础上进行一系列魔改。

代码fork过去自己改都行，pr我也会看，甚至你直接抄过去也没问题。

如果你觉得这份base code对你有帮助，请帮我点个star呜呜呜呜呜 QAQ



# 写在最后面

[![LICENSE](https://img.shields.io/badge/license-傻逼软件工程-blue.svg?style=flat-square)](https://zh.wikipedia.org/wiki/%E8%BD%AF%E4%BB%B6%E5%B7%A5%E7%A8%8B) [![LICENSE](https://img.shields.io/badge/license-傻逼肖登-orange.svg?style=flat-square)](https://github.com/SamuraiBUPT/bupt-hotel-management/blob/main/LICENSE) 
