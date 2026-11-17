# 自动盘点与定位书架

项目状态：**暂停（2026-11-17）**。用户决定暂不继续设计和实施，现阶段保存模型、仿真、选型讨论和计算结果。

最新讨论方向已改为：**摄像头外置，尽量用一只相机直接拍摄三个同款书柜**，采集后端使用 Mac 或 Linux 电脑 / NAS。按三个书柜并排、约 2.4 × 2.02 m 的假设做了取景与像素预算；候选为 Arducam B0494（108MP USB 3.0），原配镜头下初步安装距离约 2.05–2.1 m。该方案尚未完成外置三柜 3D 布局、实拍、OCR 或自动采集实现，不是已验收的盘点系统。

详见 [阶段进展、成本更正和外置相机选型](docs/progress.md) 与 [外置拍摄计算快照](data/external-camera-sizing.json)。镜面 600–2500 元及此前整柜总价已撤回，不能据此采购；标准小尺寸柱面透镜的公开价也不能直接替代当前大口径定制镜组的报价。

现有可打开的成果：

- [单摄像头 + 顶部平面镜基准模型](index.html)：柜内历史研究方案，无附加柱面透镜。
- [两片柱面透镜效果与 3D 安装光路](two-cylinder-effect.html)：真实逐面追迹对比；温和方案 L2 通光口径已缩至 100 × 28 mm，27 本示例书脊已标书名，并有“书脊正视”视角。
- [更早一轮柱面镜试算报告](optical-validation.html)：未通过的历史对照。

以下各节保留柜内光路的详细研究过程和重建方法。“当前单镜”等表述指相应保存版本，不代表最新外置方向已实现。单镜基准保留摄像头物镜和顶部平面镜 M1，附加柱面镜 L1 / L2、镜框及支柱已移除，并完成重新对焦与渲染。

## 新一轮两片柱面镜：真实效果对比

打开 [两片柱面镜效果 HTML](two-cylinder-effect.html)，可切换相机原画面、镜内裁切、几何展开、中部细节及两组镜片的 3D 安装光路。当前无柱面镜基准模型仍保留在 `index.html`，新增了效果页入口。

这次重新进行了有限光阑全视场搜索，未恢复旧的 5.57 倍处方。两片 N-BK7 圆柱面透镜与现有六片相机物镜共 15 个折射界面，真实光阑仍为 0.8 mm，传感器仍为 4000 × 2250、1.6 μm 像素；设计波长 587.6 nm。温和方案使用两片双面柱面透镜，L1 两面半径约 −58.148 / +58.148 mm、中心厚 2.5 mm、近端顶点距相机 8 mm；L2 两面半径 +65 / −65 mm、中心厚 8 mm、近端顶点距相机约 20.400 mm。当前通光窗分别为 120 × 14 mm、100 × 28 mm。L2 已按镜内有效光束包络由原420mm缩减至100mm，3D外框占位约106 × 34mm；曲率、厚度、间距和相机焦点保持原温和方案。两轮全传感器与真实光阑采样（约13万、26万条）中，L2上的镜面有效光束横向包络约89mm，90mm保留全部镜面采样光线，100mm为当前留有余量的研究尺寸，尚未计入加工及装配公差。

温和方案的相机前顶点为 (0,271.922,217.757) mm，俯仰 2.148°；M1 与当前单镜位置相同。相机后移以留出视场余量，并用实际有限光阑重新对焦。 L2改为100mm口径后已完成4000 × 2250、64条光线/像素的复算；与420mm口径的完整线性图像、全部光线通行数和书脊命中计数完全一致，结果见 `two-cylinder-v2/l2-100mm-verification.json`。高倍率方案为另一个全视场搜索结果，单独作为失败对照；具体表面、姿态和焦点见完整参数。

| 本轮相同采样规则下的指标 | 无柱面镜 | 温和方案 | 高倍率对照 |
| --- | --- | --- | --- |
| 书脊单元采样触达 | 100% | 99.68% | 96.81% |
| 书脊信号纵向跨度 | 19.6% | 31.4% | 92.6% |
| 几何 D80 光斑中位数 | 1.58 原始像素 | 2.07 原始像素 | 41.70 原始像素 |

每组完整传感器画面均为 4000 × 2250、64 条光线/像素，共 5.76 亿条发射光线。先逐面追迹相机、柱面镜及 M1，再与书本和柜体求交；没有用二维拉伸生成“光学效果”。三组使用相同示例书名、材质和照明，但各自全局曝光归一化，不能比较绝对亮度或 SNR。32/64 样本下采样触达率在本轮一致。

几何展开只从对应观测图重采样，使用同一参考书脊平面的真实主光线标定，不读清晰纹理或书名，也不按已知书本轮廓替换背景。温和方案的100个随机复核点中，有效区域映射插值 RMS 约0.072原始像素、最大约0.67像素；透明区域对应主光线受阻或逆映射未收敛。高倍率方案的映射一致性未通过（RMS约116原始像素），HTML 不将其调试展开图呈现为可靠结果，保留相机原图和镜内裁切。

结果说明：增加传感器占用不等于同等增加可读细节。温和方案仍有少量采样缺口，光斑增大；高倍率方案严重模糊。两组均未达到整排图书清晰盘点的通过标准；这不排除其他曲率、非球柱面、相机镜头或布局的方案。未验证完整衍射、宽带色差、制造公差、实拍噪声或 OCR。

- [温和方案完整数值处方](data/optics/two-cylinder-prescription.json)
- [高倍率对照处方](references/ikea-billy-oxberg/two-cylinder-v2/high-final.json)
- [前后数值比较](references/ikea-billy-oxberg/two-cylinder-v2/comparison.json)
- [独立实现、互易性及光阑验证](references/ikea-billy-oxberg/two-cylinder-v2/checks.json)
- [温和方案原生 PNG，仅镜像翻转](references/ikea-billy-oxberg/sequential-trace/v2-moderate-100mm-corrected.png)
- [高倍率原生 PNG，仅镜像翻转](references/ikea-billy-oxberg/sequential-trace/v2-high-corrected.png)

重建已保存的效果（不是重新搜索处方）：

```sh
.venv/bin/python optics/render.py --prescription data/optics/two-cylinder-prescription.json --width 4000 --spp 64 --name v2-moderate-100mm
.venv/bin/python optics/render.py --prescription references/ikea-billy-oxberg/two-cylinder-v2/high-final.json --width 4000 --spp 64 --name v2-high
.venv/bin/python optics/evaluate_cylinder_effect.py
npm run check:effects
npm run build:effects
```

## 当前单摄像头、单平面镜位置优化

打开 [index.html](index.html)：三维模型、默认真实光路、摄像头原图及几何展开图都已更新到新位置。“查看密度热图与优化对比”展示相同传感器、镜头、光阑和镜面尺寸下的前后比较。

保留六片普通旋转对称鱼眼相机物镜（11 个折射界面），不增加柱面镜；传感器仍为 6.4 × 3.6 mm、4000 × 2250 像素，真实光阑直径 0.8 mm，M1 为 580 × 52 × 1.5 mm。只改变相机和 M1 的位置、俯仰角，并调整传感器轴向位置重新对焦。

本层坐标为毫米，X 向右、Y 距层板高度、Z 距柜体前沿的深度：

| 参数 | 优化前 | 本轮数值搜索结果 |
| --- | --- | --- |
| 相机前顶点 X/Y/Z | 0 / 280 / 230 | 0 / 271.92 / 189.76 |
| 光轴向前上仰 | 4.086° | 2.148° |
| M1 中心 X/Y/Z | 0 / 299.15 / 23.53 | 0 / 282.65 / 20.59 |
| M1 切线与竖直夹角 | 40.423° | 37.863° |
| 传感器 optical Z | −16.98036 | −16.98404 |
| 全域最差采样密度 | 0.4412 px/mm | 0.5327 px/mm（+20.75%） |
| 全域采样密度中位数 | 0.8485 px/mm | 1.0975 px/mm |
| 中央 Y=125 mm 的 8 mm 字，最受压方向 | 8.83 原始像素 | 12.33 原始像素 |
| 全域最差位置的 8 mm 字 | 3.53 原始像素 | 4.26 原始像素 |
| 实际书脊稠密采样触达 | 14039 / 14039 | 14039 / 14039 |
| 书脊信号纵向包络 | 13.64% | 19.60% |

密度定义为书脊二维毫米坐标到原始传感器像素坐标映射的 Jacobian 最小奇异值。它包含剪切后的最受压方向，不能用文字外接框宽高或展开图尺寸替代。密度通过真实逐面 chief ray 的 0.1 mm 中心差分计算，并以 0.02 mm 差分复查；最差点是整排底部两端。目标 8 mm 字的最细笔画仍可能小于一个原始像素，尚未达到稳定 OCR 的清晰度要求。

搜索采用差分进化和有界 Nelder–Mead，在对称布局内优化相机 Y/Z、光轴俯仰、M1 Y/Z 和倾角。相机位于 X=0、M1 长边平行书架宽度。部件包络约束包括高于 250 mm 书顶至少 5 mm，以及距离柜体边界至少 4 mm；完整 760 × 250 mm 书脊包络须落在有限镜面和传感器内。最终稠密复核的主光线距传感器边缘至少 12.88 像素、距镜面边缘至少 1.50 mm。支架外形仍是安装参考，孔位及门铰链避让需要实测。数值搜索给出本轮找到的较好解，不是全局最优证明。

有限光阑另外复核 35 个物点，每点 256 条光线。几何光斑 D80 中位数从 1.33 增至 1.58 原始像素，最大值从 2.18 增至 2.63 像素；各物点采样光阑光线全部通过。像素密度增加不等同于同比的实际清晰度提升。相机画面以 4000 × 2250、64 条光线/像素重新渲染，共 5.76 亿条发射光线；几何展开只重采样这张观测图，未读取清晰参考图或补写书名。

- [当前安装参数](data/optics/current-layout.json)
- [当前完整镜头处方](data/optics/current-prescription.json)
- [前后数值验证与有限光阑结果](references/ikea-billy-oxberg/layout-optimization/validation.json)
- [共用色阶的密度热图](references/ikea-billy-oxberg/layout-optimization/density-comparison.png)
- [更新后的摄像头原始方向 PNG](references/ikea-billy-oxberg/sequential-trace/current-no-cylinders-raw.png)
- [数字镜像校正 PNG](references/ikea-billy-oxberg/sequential-trace/current-no-cylinders-corrected.png)
- [覆盖与代表光线路径](references/ikea-billy-oxberg/sequential-trace/current-no-cylinders-viewer.json)
- [当前布局快照](references/ikea-billy-oxberg/folded-optics-layout.json)
- [优化前单镜布局和图像](references/ikea-billy-oxberg/baseline-single-mirror/)

从已保存的当前参数重建：

```sh
.venv/bin/python scripts/prepare_no_cylinders.py
.venv/bin/python optics/validate_layout.py
.venv/bin/python optics/plot_layout.py
.venv/bin/python optics/render.py --width 4000 --spp 64 --name current-no-cylinders
.venv/bin/python optics/rectify_mirror.py
.venv/bin/python optics/rectify_pixels.py
.venv/bin/python scripts/prepare_no_cylinders.py --measure
.venv/bin/python optics/check_layout.py
npm run check
npm run build
```

继续搜索可运行 `.venv/bin/python optics/optimize_layout.py --iterations 60 --seed 41`；候选结果写入 `layout-optimization/candidate.json`，不会自动替换当前布局。`current-layout.json` 是追迹、渲染及网页模型共享的安装参数。原有 `camera-render-input.json` 为历史理想渲染输入，当前仅复用其中的 books 几何列表。

这仍是单色几何光学研究模型，尚未包含完整衍射、宽带色差、制造误差、真实噪声或实拍 OCR。默认布局显示实际逐面追迹缓存；改变书高或退距后的即时结果是针孔布局近似，静态渲染和密度图不会自动重算。

## 当前镜内内容：只根据图像边线矫正

“镜内展开”现使用纯图像流程。唯一图像输入是 [4000 × 491 镜内裁剪 PNG](references/ikea-billy-oxberg/mirror-rectification/mirror-crop.png)，其镜像方向已翻转。新脚本不读取镜头处方、3D 相机位置、书本列表、书高/宽/深度、干净贴图、已知书名或线性传感器 NPZ。

从图中检测镜框上下长边的曲线，以直线约束拟合径向去畸变；再跟踪书脊边线，用其消失点进行透视展开。当前图检出 898 个镜框边界点及 27 条共识书脊边线；拟合后镜框直线 RMS 残差约 0.44 个输入像素。图像内可见的书顶、间隙和底部背景保留原始观测内容，镜框外区域透明。可展开“查看从镜内图像提取的边线”检查特征来源。

输出 3040 × 1000 像素。仅凭单张裁剪图和直线约束不能唯一确定真实物理长宽比，因此纵向比例是展示设置，不应视为尺寸测量或更高的原始清晰度。输入观测本身仍为单色光追仿真。此前基于已知镜头及 760 × 250 mm 书脊平面的标定结果保存在 `mirror-rectification/`，HTML 默认结果改为本次图像流程。

- [当前完整校正图](references/ikea-billy-oxberg/image-based-rectification/rectified.png)
- [从图像中检出的镜框和书脊边线](references/ikea-billy-oxberg/image-based-rectification/detected-features.png)
- [当前局部放大](references/ikea-billy-oxberg/image-based-rectification/rectified-centre.png)
- [图像算法参数、假设与输入校验值](references/ikea-billy-oxberg/image-based-rectification/settings.json)
- [输出像素对应的输入坐标示例](references/ikea-billy-oxberg/image-based-rectification/pixel-sources.json)

```sh
.venv/bin/python optics/rectify_pixels.py
npm run build
```

## 历史柱面镜试算：未通过，已退出当前设计

打开 [历史柱面镜试算报告](optical-validation.html)，可查看此前带柱面镜的渲染、拆镜对照、覆盖图和完整处方。该报告已标为历史试算；当前 `index.html` 为无附加柱面镜的相机 ＋ M1 模型。

新处方包括两片 N-BK7 圆柱面透镜、PBRT 六片鱼眼相机物镜、真实孔径及 M1。使用球面/圆柱面解析求交、向量 Snell 折射和 Fresnel 透过，每条有效光线通过 15 个折射面；不再设置 115° × 18° 等效视场，不做横竖拉伸。单色设计波长 587.6 nm，传感器设计目标 6.4 × 3.6 mm、4000 × 2250、1.6 µm 方形像素，尚未选择商业相机模组。相机镜头的数值折射率来自 PBRT 研究处方，尚未对应量产玻璃牌号。

本轮原生图每像素 128 条采样光线，共 11.52 亿条；书脊 5 × 2.5 mm 单元的采样触达面积约 61.4%，并不等于可读面积。中心反向响应足迹 D80 约 0.31 mm；横向偏离约 226 mm、距层板约 125 mm 处约 7.8 mm，几何 MTF 在物方 0.5 周期/mm 下仅约 0.027。64/128 样本的几何触达面积变化约 0.021 个百分点。

数值检查覆盖 Snell 定律、全反射、柱面切向动量守恒、正反向可逆，以及 NumPy/Numba 两份实现对照。尚未与商业光学软件或实物交叉验证。已计算有限孔径几何像差及相对渐晕，完整波动衍射、宽带色差、制造公差、杂散多次反射和传感器噪声未计算。渲染使用解析实体场景与示例单色材质；不是实拍，也不是生产加工图。这一轮失败不能证明其他柱面镜或纯光路设计都不可行。

- [完整处方 JSON](data/optics/final-prescription.json)
- [原始方向 4000 × 2250 PNG](references/ikea-billy-oxberg/sequential-trace/sensor-raw.png)
- [数字镜像校正 PNG](references/ikea-billy-oxberg/sequential-trace/sensor-corrected.png)
- [详细计算结果](references/ikea-billy-oxberg/sequential-trace/results.json)
- [源数据：PBRT 鱼眼处方](https://github.com/mmp/pbrt-v4-scenes/blob/master/lenses/fisheye.10mm.dat)
- [N-BK7 材料数据](https://media.schott.com/api/public/content/41e799d0bf874807a0bb8e702fbb75b5?v=54856406)

重建流程（局部相机物镜前顶点为 Z=0，向 M1 为正）：

```sh
uv venv .venv
uv pip install --python .venv/bin/python -r optics/requirements.txt
.venv/bin/python optics/design_trial.py
.venv/bin/python optics/render.py --width 4000 --spp 128 --name sensor
.venv/bin/python optics/render.py --width 1600 --spp 64 --name no-cylinders --control
.venv/bin/python optics/analyze.py
.venv/bin/python optics/plots.py
.venv/bin/python scripts/build_optical_report.py
npm run build
```

主图使用统一显示增益；拆镜对照自动复用主图增益。对照只拆除柱面镜，未重新调焦。此处理只影响显示曝光，不影响几何追迹或足迹统计。设计脚本只优化中心近轴有限共轭并进行光阑筛选，没有完成全视场像差校正；本轮处方不应据此采购或制造。

## HTML 预览

用浏览器打开 [index.html](index.html)，即可旋转、缩放、平移模型，查看单层剖视、侧面反射光路、书脊正面和整柜安装位置。模型、贴图与渲染程序均内嵌于这一个 HTML 文件，可离线使用。

修改预览源码后执行 `npm install`、`npm run build` 重建。若需重新生成网页用 GLB，先用 Blender 运行 `scripts/export_web_model.py`。网页副本保留几何，解除 Draco 压缩，宜家原始文件单独保留。

## 历史理想模型：顶部单镜 + 柱面镜组目标方案

历史理想模型已移动摄像头、调整顶部 M1，并加入 L1 / L2 柱面镜组的曲面占位、镜架、层板下支柱与走线。M2 和扫描机构仍已移除。示例层按原网格估算底面高 1062 mm、上层板底面高 1390 mm，净空约宽 760 × 深 260 × 高 328 mm。

坐标为毫米，原点在本层柜体前沿中央，X 向右、Y 向上、Z 向柜内：

| 部件 | 中心 X / Y / Z | 尺寸与安装 |
| --- | --- | --- |
| 摄像头 C | 0 / 280 / 230 | 理想等效入瞳参考；光轴朝向 0 / 295 / 20，机身位于其后方 |
| L1 | 0 / 280.57 / 222.02 | 距 C 为 8 mm，示意窗口 32 × 12 mm、外框 38 × 18 mm |
| L2 | 0 / 281.99 / 202.07 | 距 C 为 28 mm，示意窗口 96 × 16 mm、外框 102 × 22 mm |
| M1 | 0 / 299.15 / 23.53 | 镜面 580 × 52 mm，截面切线与竖直方向夹角 40.42°；两端角码固定于上层板 |
| 中心书脊落点 | 0 / 125 / 60 | 中心总等效光程 385.18 mm |
| 示例书脊 | Z = 60 | 高 220–250 mm、深 200 mm，对齐摆放，共 27 本 |

光线由书脊经 M1 转向 L2 / L1，再进入相机。金色线展示镜组外部的理想光路，紫色虚线表示镜组内部尚未求解的等效传递；箭头按入射相机的方向绘制。柱面曲率、镜片厚度和支架是概念占位，不是可采购或加工的镜头处方。

目标假设为水平视场 115°、垂直视场 18°。有限 M1 与示意窗口的几何求交下，默认示例书脊采样面积 100% 可达，全排共同书高 0–220 mm 可见，视线与书脊面的夹角约 8.0–19.4°。仍有明显透视压缩，绿色区域不能当作文字识别率。

页面提供单层剖视、侧面光路、书脊正面、整柜位置和镜组放大；可调整书高与书脊退距。书本过高时显示部件相交或光路遮挡。默认镜面距上层板约 9.1 mm、镜面下沿比书顶高约 29.4 mm，镜组外框比书顶高约 20.8 mm，相机占位比书顶高约 16.5 mm。200 mm 深的书退后 60 mm 已用满 260 mm 净深；以上均需按实物及实际镜头重新复核。

传感器投影是无模糊的理想对照：同为 16:9 传感器、同为 115° 水平视场，普通旋转对称镜头垂直视场约 82.9°，书脊投影占画面高度约 9.2%；目标 18° 垂直视场约占 51.5%，要求约 5.57 的横竖倍率差。这只定义所需效果，没有证明两片柱面镜能以当前占位、广视场和像质实现该目标。真实折射、有限入瞳、焦距、像差、景深、照明、玻璃反光及 OCR 均未验证。

运行 `npm run check` 验证反射定律、镜面与示意窗口边界、中心落点、几何覆盖、理想投影比例和占位冲突；运行 `npm run build` 重建单文件 HTML。参数快照见 [当前光路布局](references/ikea-billy-oxberg/folded-optics-layout.json)。原始宜家 GLB 和 Blender 外形参考保持原样，新增光学部件位于 HTML 场景中。

原理资料：[柱面镜](https://www.edmundoptics.com/c/cylinder-lenses/611/)、[前表面反射镜](https://www.edmundoptics.com/knowledge-center/application-notes/optics/metallic-mirror-coatings/)。

## 历史理想渲染（已由新的逐面追迹画面替代入口）

此前生成的历史理想图保存在以下文件中；HTML 的“摄像头画面”入口现已替换为新的逐面追迹图。以下文字只描述旧的理想渲染，不适用于本轮处方。

渲染使用 Blender Cycles、1920 × 1080、96 samples，摄像头位于实际 C 点，经有限的 M1 反射；保留完整宜家柜体、玻璃门、镜框和镜组窗口框的遮挡。示例书本使用自制书名与材质，照明是设定的外部室内软光。原始相机画面存在单次反射产生的左右镜像；校正版只做水平翻转，没有拉正透视、裁切或增强文字。

柱面镜组尚无处方，渲染以理想横竖视场替代真实镜片折射。焦点、景深、像差、有限入瞳和传感器噪声未模拟；这是一张理想目标效果的物理场景渲染，不能用于判断实物文字识别率。滑块改变不会重新渲染这张静态图。

- [原始方向 PNG](references/ikea-billy-oxberg/camera-render/camera-raw.png)
- [数字镜像校正 PNG](references/ikea-billy-oxberg/camera-render/camera-corrected.png)
- [独立渲染场景](references/ikea-billy-oxberg/camera-render/camera-view.blend)
- [渲染参数与局限](references/ikea-billy-oxberg/camera-render/render-settings.json)

重建渲染后执行 `npm run build`，将预览重新嵌入 HTML：

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P scripts/render_camera_view.py
npm run build
```

渲染输入快照为 `references/ikea-billy-oxberg/camera-render-input.json`；相机和镜面参数需与当前光路一起更新。脚本在渲染前核对 Blender 相机投影与几何光线的对应关系，本次最大归一化坐标误差小于 0.000003。

## 已确认的基型

- 80 × 30 × 202 厘米，双扇全玻璃门；暂用白色模型。
- 组合标称尺寸：宽 800、深 300、高 2020 毫米。
- BILLY 裸柜标称尺寸：80 × 28 × 202 厘米；OXBERG 单扇门：40 × 192 厘米。
- 官方配置为 1 块固定搁板、4 块可调搁板；单块搁板标称承重 30 千克。

尺寸和配置来源：[宜家国际产品页](https://www.ikea.com/fi/en/p/billy-oxberg-bookcase-white-s69017828/)、[宜家中国产品页](https://www.ikea.cn/cn/zh/p/billy-bi-li-oxberg-ao-ke-bo-shu-jia-bai-se-s09184486/)。

## 模型与资料

| 内容 | 本地文件 |
| --- | --- |
| 宜家原始整柜 GLB，未改动 | [原始模型](assets/ikea/billy-oxberg/billy-oxberg-80x30x202-white-original.glb) |
| 已导入、包含贴图的 Blender 参考场景 | [Blender 场景](assets/ikea/billy-oxberg/billy-oxberg-80x30x202-white.blend) |
| 官方单独柜体 GLB | [BILLY 柜体](assets/ikea/billy-oxberg/billy-bookcase-00263850-original.glb) |
| 官方单独柜门 GLB | [OXBERG 玻璃门](assets/ikea/billy-oxberg/oxberg-glass-door-90275617-original.glb) |
| 从实际 GLB 渲染的预览 | [模型预览](references/ikea-billy-oxberg/model-preview.png) |
| 中国款柜体装配说明 | [柜体说明](references/ikea-billy-oxberg/billy-bookcase-assembly.pdf) |
| 中国款玻璃门装配说明 | [柜门说明](references/ikea-billy-oxberg/oxberg-glass-door-assembly.pdf) |
| 来源、下载时间及文件校验值 | [来源清单](references/ikea-billy-oxberg/sources.json) |
| 实际模型包围盒检查结果 | [模型检查](references/ikea-billy-oxberg/model-inspection.json) |

Blender 场景以米为底层单位、毫米为显示单位，X 为宽度，Y 为深度，Z 为高度，柜门朝向 -Y。`IKEA original reference` 集合保留原模型几何；`Design additions` 集合可加入传感器、支架和走线；另一集合仅用于预览摄影。没有根据标称尺寸强制缩放原模型。

重建 Blender 场景和预览：

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/prepare_ikea_reference.py
```

## 来源与精度边界

2026-11-17 从宜家公开的网页 3D 展示资源取得国际组合款 **690.178.28**，组合为 BILLY **002.638.50** ×1 与 OXBERG **902.756.17** ×2。中国产品页 **091.844.86** 对应 BILLY **103.515.68** ×1 与 OXBERG **702.756.18** ×2；两者标称外形尺寸一致。本项目保留的中文装配资料对应中国产品页。

原始 GLB 为 glTF 2.0，带 Draco 压缩及 WebP 贴图。它是轻量网页展示网格，按材质合并为 3 个网格对象，没有柜门开合或层板调节的装配关系。单独柜体与柜门模型另行保留，方便后续建立装配参考。

整柜网格包围盒约为 **800.31 × 319.51 × 2024.94 毫米**，包含突出部件及展示网格的近似误差。方案布局以 **800 × 300 × 2020 毫米**的官方标称尺寸为基准。涉及支架配合、孔位、板厚、门缝、铰链避让的加工尺寸，需要按中国款装配资料和实物测量确认；此模型可用于外形与设备布置参考。

模型和产品图的权利归各自权利人；本仓库的整理与格式转换不改变原始素材的授权状态。
