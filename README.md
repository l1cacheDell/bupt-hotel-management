# bupt hotel management system
波普特廉价酒店管理系统，北京邮电大学2023年秋季-软件工程-课程设计。

> 用心做好一件事。

> 在软件开发的生命周期中，软件维护才是耗时最多的环节。

这虽然是2023年秋季的软件工程课程设计，但是至今仍在维护，我看到了有很多后人star这个仓库，说明它还在发挥它的作用。维护这个仓库，做好一份代码，是一件很有意义的事情。

# 分支说明

您目前正在：**backend Python分支**

Dependency:

```bash
python -m venv hotel_venv

# windows
./hotel_venv/Scripts/activate
# linux/macos
source hotel_venv/bin/activate

pip install tortoise-orm aiosqlite fastapi uvicorn
```

# News

+ [2024-09-14] 计划重写Python后端，舍弃旧的Flask + pymysql框架，选用FastAPI + asyncio + Tortoise ORM & aiosqlite.
+ [2024-04-11] 新增golang后端，对协程提供更好的支持。
+ [2023-12-17] 完成Python后端的搭建，完成基于Vue的前端的初步搭建。

# 技术栈详情
+ Vue3 (axios, element-plus)
+ Python backend: Flask + pymysql
+ Golang backend: Gin + GORM

# 任务分析
## 1. 波普特酒店管理系统宏观分析
波普特酒店管理系统这个任务，本质上是一个IO bound的系统，也就是说可能系统的bottleneck大多数都在IO上面（与数据库进行IO）.既然是一个IO Bound的task，一门支持协程的语言是很有必要的。

协程本质上的思想，就是在一个coroutine挂起的时候，去执行另一个协程。比如：

+ A协程遇到了网络请求IO，或者数据库IO（等待其他人完成工作，自己只是在等待）
+ 这个时候，我们会选择把A协程挂起。因为这是无意义的等待，这个等待时间我们完全可以执行其他事情。
+ 挂起A协程，执行B协程
+ 等A协程完成了IO，我们再执行A协程后续的代码段

这就是协程最基本的思想，通过挂起IO等待中的协程，计算其他协程的任务，以提高整个系统的并发量，从而提高请求的吞吐量。

所以选用一门对协程有很好支持的语言，对于我们的任务是至关重要的，我们主要使用了Python + Golang这两门语言。

__为什么？__

+ 避免选择小众的语言，比如说Elixir其实也是一门很不错的语言，可惜它的设计思想一般人无法理解，也很难上手，所以不选择
+ 时间花在刀刃上：不用浪费时间去学一门xx语言，大家时间都很宝贵。选用一门完成这个课设，也得考虑到今后自己的发展、就业趋势，浪费时间学一门看似正确的语言，在一个很长的时间维度上，被证明是错误的。
+ “Why not Rust？” 请Rust布道者立刻关闭本页面。

## 2. 软件工程课设需求与测试接口说明

我们考虑到软件工程这门课程对于波普特廉价酒店管理系统的核心要求：

+ **时间片调度、以风速为优先级**

最初觉得这个需求特别奇怪，因为整个时间片调度的核心原因是风速：高风速的优先调度（优先满足）。我们认为可能仅仅是老师想构建一个**可以被调度的依据**，至于这个依据的可行性、科学性，都是不考虑的。

所以有了这样一个怪异的需求，我们也只能尽可能满足。

所以我们在软件工程课设的跨组联调的时候（多个不同的组互相发送请求测试），我们为了保证多组内能够顺利完成联调、处理接口，定义了一套公用的、公开的接口：

https://apifox.com/apidoc/shared-14253c1e-942e-4899-a2ce-56f935bf571a

这个接口文档中，我们没有定义一些数据库查询接口、自身的前后端接口（我们认为那些都是可以组内自行确定的，不属于公共的联调内容），只定义了通用的、所有人都要满足的接口。

后人在开发过程中，也可以依据该API接口文档进行开发，这样如果后面又遇到跨组联调的场景，不至于手忙脚乱。

## 3. 数据库表的设计

在设计数据库表之前，我们先要思考哪些操作会用到数据库：

1. 从交互层面来看，用户的入住、退房、开启空调、关闭空调、调整温度、调整风速、主动查询房间信息；会用到数据库。
2. 从后端的调度层面来看：被时间片调度到`serving_queue`里面的房间，会计费；在`waiting_queue`中的房间，不会被计费。

我们设计：

__一、用户表__

+ id：int，主键，自增
+ 用户名字：string
+ 用户身份证号：string
+ 用户房间号：int （注意这个房间号不是用户自己选择的，而是系统分配的，毕竟没有人在入住的时候可以选择到底是哪个号码）（同时这个也是一个**foreign key**）
+ 用户入住时间：datetime
+ 用户离开时间：datetime，可以为空，因为中间状态用户可能没有离开房间
+ 用户账单：float

这个表格的主键为id，无实际意义

__二、房间表__

+ 房间号：int，主键
+ 状态：string，有“available”, “occupied”两种状态
+ 房间风速：string，有“high”, “medium”, “low”三种状态
+ 房间温度：float

__三、详单表__

在软件需求说明书中，明确指出了：需要前端提供一个详单表，那么我们在这里在后端把详单进行记录。

详单的意思是：每一个操作对应的扣费数额。具体来说有以下字段：

+ id：int，主键，自增，无实际意义
+ 用户名字：string
+ 房间号：int
+ 操作类型：string。因为详单这里我们只记录空调开销，所以操作类型也只有**针对空调风速操作**的几种，至于其他的，什么房费、什么饮料费其他杂项费用，不记录在此。所以操作类型有：“high”，“medium”，“low”，分别代表空调的三种风速。开空调默认为medium风速。所以开关空调、调整空调风速，都会在这里有操作的记录。
+ 开始时间：datetime
+ 结束时间：datetime，不可以为空。我们程序中会维护一个数据结构，它负责记录每一个操作的起始与结束。只有一个操作结束了之后，会被记录到这个表格中。对于正在serving而没有结束的状态，会在程序中的数据结构里面做记录，不能落到这个持久化层来。
+ 扣费数额：float，单位是元。

这个表格有两个操作来源：第一个是用户自己的行为（调整风速之类的），第二个是后端的行为：时间片调度，会不停地对这个表格新增记录进来。

## 4. 调度设计：Scheduler的数据结构
我们维护一个scheduler，这个scheduler负责迭代。同时这个scheduler运行在另一个线程中。

Scheduler内部会动态维护几个数据结构：

+ RoomServe哈希表，`key`是房间号，`value`是一个字典：房间的风速：`high`, `medium`, `low`三种状态。房间的温度：浮点数。
+ serving_queue：当前轮到**应该提供送风**的房间队列
+ waiting_queue：当前**等待送风**的房间队列
+ DBQueue：是一个自己用的小型queue。用来存放需要更新的房间信息。

serving_queue和waiting_queue中存放的，是结构体`schedule_item`。

schedule_item:

+ room_number：房间号
+ start_time：开始时间
+ end_time: 结束时间
+ speed：房间风速

DBQueue中存放的，是结构体db_queue_item。

db_queue_item:

+ room_number：房间号
+ op_type：操作类型，有`temperature`和`speed`两种。
+ op_value：操作值，如果是`temperature`，则值就是用户新设置的温度值，为了统一，在这里以字符串传递。如果是`speed`，那么值就是`high`, `medium`, `low`中的一个。
+ start_time：开始时间
+ end_time: 结束时间



## 5. 调度算法：Scheduler的调度设计

一共有两个线程，一个是主线程，另一个是Scheduler线程。

SchduleTask结构体内部的成员：

+ room_number：房间号
+ op_type：操作类型，有`temperature`和`speed`两种。
+ op_value：操作值，如果是`temperature`，则值就是用户新设置的温度值，为了统一，在这里以字符串传递。如果是`speed`，那么值就是`high`, `medium`, `low`中的一个。



两个线程讲解：

+ 主线程：负责接收来自外部的请求，这些请求全部都化为`ScheduleTask`对象，放入`task_queue`中。**不允许来自FastAPI的请求直接对数据库进行IO操作，因为这样没有经过schedule，会导致进入未知的状态。**
+ Scheduler线程：有一个`need_step()`方法，判断是否需要进行step，如果返回true，就会调用`step()`方法。
    + `step()`方法首先会先锁住`task_queue`，不允许主线程继续往这个里面添加任务，相当于阻塞住。
    + 然后自己从`task_queue`中把所有的`ScheduleTask`对象取出来，更新RoomServe哈希表，把每个房间需要更改的地方更改了。同时把**改变温度**的ScheduleTask转换一下，放到`DBQueue`中。
    + 然后解锁对`task_queue`的占有状态，允许主线程往里面添加task。避免长时间阻塞主线程。
    + 现在状态已经更新了，那么就开始调度Scheduler，以风速为优先级，更新`serving_queue`和`waiting_queue`。从`serving_queue`里面退出来的`schedule_item`，全都记录上结束时间，然后把这个schedule_item转化一下，放入`DBQueue`中。
    + 最后再进行持久化操作：把`DBQueue`中的数据依次pop出来，写入数据库，清空`DBQueue`。



决定是否`step()`的关键是：是否有需要时间片的需求，如果有，则step，如果没有，就不需要step了。因为你不能保证所有操作都能在一个tick内执行完，你也不能保证tick到了之后，step的调用是否会堆积。

设置两个queue的长度为3和2，因为这是验收时候的标准。



__案例__

如果我的房间是**高风速**，正在被serving，这个时候我突然把风速调为了medium，在程序里面应该是一个怎样的状态呢？

首先递交到请求侧——请求线程封装为schedule_task——scheduler线程开始step，锁住task_queue，读取到task，解包，更新底层的RoomServe哈希表——更新serving_queue——大概率这个时候，房间已经从serving_queue中被踢出了（因为风速优先级太低了），然后被转化为了DBQueueTask，放入DBqueue——`step()`函数尾部：把DBQueue一一出队，持久化到数据库中。

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
