# 电商线索与客服表格自动化 / E-commerce Lead Automation

[English](README.md) | **简体中文**

把一份脱敏的电商留言表变成可审核的跟进队列：上传 Excel/CSV，自动判断意向、客户类型，生成待人工确认的回复草稿和销售跟进动作，再按漏斗阶段导出结果。

这是一个可现场演示、可按模块交付的公开案例，适合淘宝/拼多多/Shopify 小商家和代运营团队。默认使用本地规则和合成数据，不需要 API Key；真实 AI 是显式可选能力，费用与数据流向由客户在启用前确认。

![E-commerce Lead Automation 结果页](screenshots/result.png)

## 五分钟演示

1. 点击“载入示例数据”（示例联系方式是 `demo-contact-001` 这类合成标识，不是真实手机号）。
2. 选择“电商咨询”“售后”或“B2B 询价”行业预设，也可以保留自定义配置。
3. 使用“演示规则”处理，查看高/中/低意向、回复草稿和跟进动作。
4. 选中一行，编辑并确认最终回复，再把线索阶段调整为“新线索 / 已联系 / 待补信息 / 已转交”。
5. 下载全部草稿、待复核或可发送结果；“可发送”只包含人工确认且再次通过安全检查的行。

## 功能

- 支持 `.xlsx` / `.csv`（UTF-8、GB18030 等常见编码）
- 无 API Key 的离线演示模式
- 可选 OpenAI 兼容 API
- 可下载标准 Excel 模板，上传后自动识别常见的客户留言列
- 保留原始列，追加意向等级、客户类型、线索阶段、客户回复、最终回复、回复状态、跟进动作、处理状态和判断依据
- `客户回复`是 AI 草稿；`最终回复`是人工确认后才建议对外发送的文本；`回复状态`为“待确认”“已确认”或“待复核”
- 结果支持按意向等级、处理状态筛选和排序，可选择单行查看并复制回复
- 提供电商咨询、售后、B2B 询价三个行业预设；预设只填充当前会话的行业说明和语气
- 每行提供会话内“线索阶段”漏斗字段：新线索、已联系、待补信息、已转交；不建立账号或服务端历史库
- 单行失败不影响其余结果，可下载待复核行
- 完整结果会导出为“全部结果 / 高意向 / 待复核 / 使用说明”四个草稿工作表；另有只包含已人工确认安全行的“可发送”工作表
- 输入表若已有同名结果列，会自动给 AI 结果列加“（AI）”后缀，不覆盖原数据
- 导出时会拦截 Excel 公式注入，避免留言或回复被当成可执行公式
- 页面提供一份默认标签草案和内置禁词初稿，供客户用真实样表校准；标签草案不会自动改变当前输出标签，两者都不是平台完整规则
- 导入的非法线索阶段会回退为“新线索”，并标记“待复核”；原始列不会被覆盖

## 本地运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PORT=8501 bash start.sh
```

打开 `http://localhost:8501`，点击“载入示例数据”即可体验；也可以先点击“下载 Excel 模板”，替换模板中的合成示例行后上传。

### Windows PowerShell

项目要求 Python 3.10 或更高版本，Windows 推荐 Python 3.11/3.12。Windows 不使用 `start.sh`、`source` 或 `python3`。在项目目录打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

如果激活脚本被系统策略拦截，可跳过激活，直接调用 `.\.venv\Scripts\python.exe`。正式交付前仍应在客户的目标 Windows 环境复测安装、启动、上传和导出流程。

如需在 PowerShell 中显式开启真实 AI（请先确认数据合规），环境变量写法是：

```powershell
$env:COMMERCE_LEAD_ENABLE_REAL_AI = "true"
$env:OPENAI_API_KEY = "your-key"
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"  # 可选
$env:OPENAI_MODEL = "gpt-4o-mini"                    # 可选
```

## 操作流程

1. 上传已脱敏的 Excel/CSV（或载入示例数据），确认自动识别的客户留言列。
2. 在“业务回复设置”中填写产品/行业说明，选择回复语气、禁止类别和自定义禁词。
3. 点击“保存回复设置”；设置只保存在当前浏览器会话，不会写入文件或长期持久化。
4. 选择演示规则或真实 AI，点击“开始处理”。修改设置后，需显式点击“按新设置重新生成”。
5. 在结果表中选择一行，查看 AI 草稿；如需采用草稿，点击“采用 AI 草稿并编辑”，再编辑并点击“保存并确认”。只有“已确认”的最终回复才会进入可发送清单。
6. 下载全部草稿结果、可发送结果，或仅下载待复核行。

示例处理结果会在原始留言旁追加以下字段：

| 字段 | 用途 |
| --- | --- |
| 意向等级 / 客户类型 | 帮销售快速分组和排序 |
| 线索阶段 | 当前会话的跟进漏斗：新线索、已联系、待补信息、已转交；导出后由人工继续维护 |
| 客户回复 | AI 生成的回复草稿；最多追问一个关键缺口，需人工复核 |
| 最终回复 | 默认空白；人工编辑并通过安全检查后，保存为“已确认”才准备对外发送 |
| 回复状态 | `待确认`、`已确认` 或 `待复核`；待复核行不可直接发送 |
| 跟进动作 | 销售内部的下一步提醒，例如确认规格、收集订单号或准备报价资料 |
| 处理状态 / 判断依据 | 标记成功、空内容或待复核，并说明分类依据 |

例如，客户留言“想采购 100 件，预算 2 万元”，结果会引用“100 件”和“2 万元”，并优先询问尚未提供的规格或型号；它不会凭空承诺价格、库存、折扣或交期。

运行测试：

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest -q tests
```

## 回归验证

仓库内的 `tests/fixtures/golden.xlsx` 是一份脱敏合成的 15 行回归样本，覆盖询价、代理合作、低意向、售后、空留言和公式样式文本。配套的 `tests/fixtures/golden.meta.json` 记录期望值来源（当前为作者先验 `author_prior`）、最后人工复核日期，以及 verified/unverified 样例；其中 `expectation_source_by_id` 明确把 `T01`、`T04`、`T08` 标为 `unverified`。这三条分类尚未经过客户语料校准，测试只检查它们的行数、字段格式和处理/回复状态；只有 verified 样例参与分类回归断言。这不是业务准确率承诺，客户提供标注样例后应重新校准基线。`tests/test_golden_fixture.py` 还固定验证行号和导出安全边界；它不锁死 AI 自然语言文案。修改分类规则或导出流程后，应先运行：

```bash
PYTHONPATH=. pytest -q tests/test_golden_fixture.py
```

## 回复配置与安全后检

配置表单的四个字段都有边界：产品/行业说明最多 800 个字符；语气只能选“专业、亲切、简洁、稳重”；禁止类别只能从价格、库存、折扣、交期、售后结论、效果保证六类中选择；自定义禁词最多 20 个，每个最多 40 个字符，合计最多 400 个字符。配置只在当前会话生效，不会持久化；换文件会恢复默认配置。

生成或编辑回复后，系统会做安全后检：拦截结果承诺、价格/库存/折扣/交期/售后/效果保证等配置类别和自定义禁词命中，并将相关行标为“待复核”。AI 草稿不会自动写入“最终回复”；“采用 AI 草稿并编辑”只会把草稿放入编辑框，仍需人工保存并确认。“待复核”规则是处理状态非“成功”、回复状态为“待复核”，或最终回复在当前配置下未通过安全检查。请始终检查客户事实、价格、库存、交期和售后承诺，不要把 AI 草稿直接发送。

内置禁词初稿位于 `services/policy_defaults.py`，页面可展开查看。默认标签和禁词都是接单前的校准起点，不代表已经针对某家店铺完成校准，也不是任何平台的完整规则库。

页面页脚会显示进程启动时捕获的短提交 SHA；演示前先与 `git rev-parse --short HEAD` 对照，避免托管实例仍在运行旧代码。

完整草稿结果导出为四个工作表：`全部结果`、`高意向`、`待复核`、`使用说明`，并带有“原始行号”和“导出用途”水印。单独的“可发送”导出只包含处理成功、人工标记“已确认”且在导出时再次通过安全检查的行。所有导出都会转义以 `=`, `+`, `-`, `@` 开头的单元格和表头，避免 Excel 公式注入；不会导出 index、row_id 或 API key 等内部字段。

## 真实 AI 模式

为避免公开 Demo 意外消耗密钥，真实 AI 需要同时显式打开开关和配置凭据。禁止把密钥写入代码或提交到 Git：

```bash
export COMMERCE_LEAD_ENABLE_REAL_AI="true"
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选
export OPENAI_MODEL="gpt-4o-mini"                   # 可选
```

真实模式每次最多处理 200 行，每个浏览器会话累计最多处理 200 行；上传真实客户数据前，请确认所用模型服务的合规要求。

### 处理量分层建议

- 免费试跑：建议单次不超过 100 行，留出额度余量。
- 付费校准：单次不超过 200 行；达到会话上限后需关闭页面重新打开新批次。
- 规则/演示版：单次最多 5,000 行，纯本地、不调用外部模型，但分类能力需要按客户样本单独校准。

## 限制与数据边界

- 单文件最大 10 MB，最多 5,000 行；真实 AI 模式额外限制为 200 行。
- 单条留言发送给真实模型时最多 4,000 个字符，模型输出字段有长度和枚举校验。
- 真实 AI 只有在同时设置 `COMMERCE_LEAD_ENABLE_REAL_AI=true` 和 `OPENAI_API_KEY` 时才可选；页面会显示单批次/单会话行数护栏和外部模型费用提示。
- 产品当前没有登录、权限和历史任务；上传内容只保存在当前会话内，服务不会主动长期保存文件。若要把真实 AI 开关放到公网，建议先加登录或放在受控内网。
- 真实 AI 模式会把留言发送到你配置的 OpenAI 兼容服务，并可能产生 API 费用；请先脱敏，不要上传密码、身份证号、支付信息或其他不必要的敏感数据。
- 演示模式完全离线，只用于展示流程，不代表真实模型效果。

## 客户交付边界

- 这是当前浏览器会话内的处理工具；不会替客户自动登录店铺、自动发送消息、绕过平台风控或保存账号历史。
- 客户上传前应自行脱敏；真实 AI 会把留言发送到所配置的 OpenAI 兼容服务，服务商的数据留存和费用由客户确认。
- “可发送”只是人工复核后的导出标签，不是平台发送接口，也不承诺价格、库存、交期、售后结论或转化率。
- 行业预设是接单前的校准起点；客户应提供脱敏样本确认标签、禁词和交付格式。

安全问题和负责任披露流程见 [SECURITY.md](SECURITY.md)，依赖许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 已知限制与接单边界

陌生电商格式中的平台标签、图片链接、重复买家、空行、合并单元格和多工作表都需要先用客户样表确认；当前真实 AI 类别不是任意自定义标签，且真实 AI 单文件/单会话最多 200 行。产品不承诺千牛自动发送、图片识别、自动合并或平台零处罚。发送隔离、可发送导出和导出时安全复核仍不能替代客户最终审核或平台合规检查。

## 目录

```text
app.py
services/
  excel.py
  funnel.py
  industry_presets.py
  results.py
  classifier.py
  reply.py
  model_client.py
examples/demo.csv
tests/
```

## English summary

E-commerce Lead Automation turns customer-message spreadsheets into an auditable e-commerce lead queue. Upload an XLSX/CSV file, choose an industry preset, process it offline with deterministic rules (or explicitly enable an OpenAI-compatible endpoint), review the draft, set a session-only funnel stage, edit and confirm the final reply, then download a draft or sendable workbook. `客户回复` is a draft; `最终回复` stays empty until a person confirms it. The sendable export performs a safety recheck and includes only successful, confirmed rows. Demo contacts use synthetic IDs, and real AI calls may incur cost and send data to the configured service.
