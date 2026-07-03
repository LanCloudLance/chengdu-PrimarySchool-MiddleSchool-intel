<!-- OPENPRD:GENERATED
adapter=codex
source=openprd-frontend-design:reference:design-asset-contract.md
version=0.1.11
checksum=f9fe5859128caa7f
-->

# 设计资产合同

## 目标

让“做界面”先有事实源和资产源，而不是先堆样式。

## 最小合同

每个前端体验任务，先明确这几类信息是否存在：

| 维度 | 需要什么 | 缺失时怎么办 |
| --- | --- | --- |
| 产品事实 | 产品名、版本、发布时间、关键规格、价格、引用数据 | 先写进 `facts-sheet.md`，未知就标 `待确认` |
| 品牌资产 | logo、品牌色、字体、口号、icon 风格 | 先写进 `asset-spec.md`，没有就说明缺口 |
| 内容资产 | 产品图、场景图、摄影图、插图、图表、馆藏图、案例图 | 先写进 `asset-spec.md` 或 `image-preflight.md` |
| 参考资产 | 用户给的效果图、设计稿、参考截图、参考站点局部 | 先写进 `asset-spec.md` 或 `selected-direction.md`，并声明它是不是主参考源 |
| 布局资产 | 这次要用的 layout skeleton | 从 `.openprd/design/layouts/` 选，不临场发明 |
| 组件资产 | 这次要用的 hero、stat、feature-grid、timeline 等 | 优先用 `.openprd/design/components/` 里已有结构 |

## 禁止行为

- 没核实事实就直接写产品页。
- 没拿到真实内容图却先做内容型页面的大面积版式。
- 用户已经给了效果图，却还把样式库默认风格当成更高优先级。
- 一边实现一边临时发明主题、组件和布局体系。

## 完成标准

- 事实写进 `facts-sheet.md`
- 素材写进 `asset-spec.md`
- 必要图片判断写进 `image-preflight.md`
- 方向差异写进 `direction-plan.md`
- 选中方向写进 `selected-direction.md`
- 若已有用户参考图，要明确记录它是否是当前实现的主参考源
