<template>
  <div class="map-layout">
    <div ref="canvasRef" class="map-canvas">
      <svg
        class="map-svg"
        :class="{ grabbing: dragging }"
        @mousedown="startPan"
        @wheel.prevent="onWheel"
      >
        <defs>
          <pattern id="clean-fresh" width="8" height="8" patternUnits="userSpaceOnUse">
            <rect width="8" height="8" fill="#dcfce7" />
            <path d="M0 8 L8 0" stroke="#16a34a" stroke-width="1.4" />
          </pattern>
          <pattern id="clean-normal" width="8" height="8" patternUnits="userSpaceOnUse">
            <rect width="8" height="8" fill="#fef9c3" />
            <path d="M0 8 L4 4 L8 0" stroke="#ca8a04" stroke-width="1.2" />
          </pattern>
          <pattern id="clean-stale" width="8" height="8" patternUnits="userSpaceOnUse">
            <rect width="8" height="8" fill="#fee2e2" />
            <path d="M0 8 L8 0 M-2 2 L2 -2 M6 10 L10 6" stroke="#dc2626" stroke-width="1.4" />
          </pattern>
          <pattern id="clean-never" width="8" height="8" patternUnits="userSpaceOnUse">
            <rect width="8" height="8" fill="#f1f5f9" />
            <circle cx="4" cy="4" r="1" fill="#94a3b8" />
          </pattern>
          <marker id="pipe-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="#2563eb" />
          </marker>
        </defs>

        <g :transform="`translate(${view.tx} ${view.ty}) scale(${view.k})`">
          <!-- 底图道路 -->
          <g class="road-layer">
            <path
              v-for="road in roads"
              :key="road.name"
              :d="roadPath(road.path)"
              class="road-base"
              :class="{ dimmed: activeRoad && activeRoad !== road.name }"
            />
            <text
              v-for="road in roads"
              :key="`${road.name}-label`"
              :x="road.path[0][0] + 12"
              :y="road.path[0][1] - 18"
              class="road-label"
              :class="{ dimmed: activeRoad && activeRoad !== road.name }"
            >{{ road.name }}</text>
          </g>

          <!-- 选中设施的排水管走向 -->
          <polyline
            v-if="selectedPipe"
            :points="linePoints(selectedPipe)"
            class="pipe-line"
          />

          <!-- 点位 -->
          <g
            v-for="point in locatedPoints"
            :key="`${point.kind}-${point.id}`"
            class="map-point"
            :class="{ dimmed: pointDimmed(point), selected: isSelected(point) }"
            @click.stop="choosePoint(point, true)"
          >
            <!-- 积水历史次数：右侧短杠排列，颜色随次数加重 -->
            <g class="flood-ticks">
              <line
                v-for="n in Math.min(point.floodCount, 5)"
                :key="n"
                :x1="markerShape(point).x + 11"
                :x2="markerShape(point).x + 11 + tickLen(n)"
                :y1="markerShape(point).y - 6 + (n - 1) * 4"
                :y2="markerShape(point).y - 6 + (n - 1) * 4"
                :class="floodClass(point.floodCount)"
                stroke-width="2"
                stroke-linecap="round"
              />
            </g>

            <!-- 设施=方井，雨水口=圆箅 -->
            <rect
              v-if="point.kind === 'facility'"
              :x="markerShape(point).x - 9"
              :y="markerShape(point).y - 9"
              width="18"
              height="18"
              rx="3"
              :fill="cleanFill(point)"
              :stroke="pointStroke(point)"
              :stroke-dasharray="point.lastClean ? 'none' : '3 2'"
              stroke-width="2"
            />
            <circle
              v-else
              :cx="markerShape(point).x"
              :cy="markerShape(point).y"
              r="8"
              :fill="cleanFill(point)"
              :stroke="pointStroke(point)"
              :stroke-dasharray="point.lastClean ? 'none' : '3 2'"
              stroke-width="2"
            />

            <text
              :x="markerShape(point).x"
              :y="markerShape(point).y + 24"
              class="point-label"
              text-anchor="middle"
            >{{ point.code }}</text>
            <text
              v-if="point.floodCount > 5"
              :x="markerShape(point).x + 40"
              :y="markerShape(point).y - 2"
              class="flood-plus"
              :class="floodClass(point.floodCount)"
            >{{ point.floodCount }}次</text>

            <text
              v-if="!point.lastClean"
              :x="markerShape(point).x"
              :y="markerShape(point).y - 14"
              class="never-badge"
              text-anchor="middle"
            >未清掏</text>
          </g>
        </g>
      </svg>

      <!-- 图例与控件 -->
      <div class="map-toolbar">
        <select v-model="roadFilter" class="road-select" @change="onRoadChange">
          <option value="">全部道路</option>
          <option v-for="road in roads" :key="road.name" :value="road.name">{{ road.name }}</option>
        </select>
        <button class="btn" type="button" @click="zoomBy(1.25)">放大</button>
        <button class="btn" type="button" @click="zoomBy(0.8)">缩小</button>
        <button class="btn" type="button" @click="resetView">复位视野</button>
      </div>

      <div class="map-legend">
        <div class="legend-title">排列编码</div>
        <div class="legend-row"><svg width="26" height="18"><rect x="4" y="2" width="16" height="14" rx="2" fill="url(#clean-fresh)" stroke="#16a34a" stroke-width="1.5"/></svg><span>上次清掏 ≤30 天</span></div>
        <div class="legend-row"><svg width="26" height="18"><rect x="4" y="2" width="16" height="14" rx="2" fill="url(#clean-normal)" stroke="#ca8a04" stroke-width="1.5"/></svg><span>31–90 天</span></div>
        <div class="legend-row"><svg width="26" height="18"><rect x="4" y="2" width="16" height="14" rx="2" fill="url(#clean-stale)" stroke="#dc2626" stroke-width="1.5"/></svg><span>超过 90 天</span></div>
        <div class="legend-row"><svg width="26" height="18"><rect x="4" y="2" width="16" height="14" rx="2" fill="url(#clean-never)" stroke="#64748b" stroke-width="1.5" stroke-dasharray="3 2"/></svg><span>从未清掏</span></div>
        <div class="legend-row"><svg width="34" height="18"><line x1="4" y1="5" x2="30" y2="5" class="tick-high" stroke-width="2" stroke-linecap="round"/><line x1="4" y1="10" x2="24" y2="10" class="tick-high" stroke-width="2" stroke-linecap="round"/><line x1="4" y1="15" x2="18" y2="15" class="tick-high" stroke-width="2" stroke-linecap="round"/></svg><span>右侧短杠数＝积水历史次数（≥5 红、3–4 橙、&lt;3 蓝）</span></div>
      </div>

      <div v-if="loading" class="map-hint">分布数据加载中…</div>
      <div v-if="loadError" class="map-hint error">{{ loadError }}</div>
    </div>

    <!-- 右侧明细：点开某处看到管段走向与关联诉求 -->
    <aside class="map-detail">
      <template v-if="detail">
        <header class="detail-head">
          <div>
            <span class="detail-kind">{{ detail.kind === 'facility' ? '排水设施' : '雨水口' }}</span>
            <strong>{{ detail.code }}</strong>
          </div>
          <button class="link" type="button" @click="clearSelection">关闭</button>
        </header>
        <p v-if="detailError" class="map-hint-inline error">{{ detailError }}</p>
        <p v-if="detailLoading" class="muted-text">明细加载中…</p>

        <dl class="detail-grid">
          <div><dt>名称形式</dt><dd>{{ detail.name ?? '—' }}</dd></div>
          <div><dt>所在道路</dt><dd>{{ detail.road ?? '—' }}</dd></div>
          <div><dt>当前状态</dt><dd>{{ detail.status ?? '—' }}</dd></div>
          <div>
            <dt>上次{{ detail.kind === 'facility' ? '清疏' : '清掏' }}日</dt>
            <dd :class="{ missing: !detail.lastClean }">{{ detail.lastClean ?? '从未清掏' }}</dd>
          </div>
          <div>
            <dt>积水历史次数</dt>
            <dd :class="floodClass(detail.floodCount)">{{ detail.floodCount }} 次</dd>
          </div>
          <div v-if="detail.crew"><dt>责任班组</dt><dd>{{ detail.crew }}</dd></div>
          <div v-if="detail.facilityCode"><dt>关联设施</dt><dd>
            <button class="link" type="button" @click="jumpFacility(detail.facilityCode)">{{ detail.facilityCode }}</button>
          </dd></div>
        </dl>

        <div v-if="detail.missing.length" class="missing-box">
          资料待补：{{ detail.missing.map(missingLabel).join('、') }}
        </div>

        <section class="detail-section">
          <h4>排水管走向</h4>
          <div v-if="detail.pipePath" class="pipe-chart">
            <svg viewBox="0 0 300 120">
              <polyline
              :points="miniPolylinePoints"
              class="mini-pipe"
              marker-end="url(#pipe-arrow)"
            />
            <circle
              v-for="(node, index) in detail.pipePath"
              :key="index"
              :cx="miniX(node)"
              :cy="miniY(node)"
              r="3.5"
              fill="#2563eb"
            />
              <text x="6" y="14" class="mini-note">起点 {{ detail.code }}</text>
              <text x="196" y="112" class="mini-note">下游出水方向 →</text>
            </svg>
            <ol class="pipe-nodes">
              <li v-for="(node, index) in detail.pipePath" :key="index">
                节点 {{ index + 1 }}：({{ node[0] }}, {{ node[1] }})
              </li>
            </ol>
          </div>
          <p v-else-if="!detail.hasCoord" class="muted-text">该点暂无坐标，管段走向需补测后展示。</p>
          <p v-else-if="kindOfMissing('管段走向')" class="muted-text">坐标已有，管段走向资料待补。</p>
          <p v-else-if="detail.kind === 'inlet'" class="muted-text">雨水口接入 {{ detail.facilityCode ?? '所属设施' }}，管段走向见所属设施。</p>
          <p v-else class="muted-text">暂无管段走向记录。</p>
        </section>

        <section class="detail-section">
          <h4>关联诉求记录（{{ detail.complaints?.length ?? 0 }}）</h4>
          <ul v-if="(detail.complaints ?? []).length" class="complaint-list">
            <li v-for="item in detail.complaints" :key="String(item.id)">
              <div class="complaint-top">
                <strong>{{ item['诉求编号'] }}</strong>
                <span class="complaint-status">{{ item['诉求状态'] ?? item.status }}</span>
              </div>
              <p>{{ item['诉求内容'] }}</p>
              <span class="muted-text">{{ item['诉求来源'] }} · 期限 {{ item['办理期限'] }} · {{ item['处理措施'] }}</span>
            </li>
          </ul>
          <p v-else class="muted-text">暂未关联诉求记录。</p>
        </section>
      </template>

      <template v-else>
        <header class="detail-head">
          <strong>点位明细</strong>
        </header>
        <p class="muted-text">点击图上的排水设施（方形）或雨水口（圆形），可查看排水管走向、积水历史与关联诉求。台账列表里点行也能定位到这里。</p>
        <div v-if="summary" class="detail-stats">
          <div><strong>{{ summary.facilityCount }}</strong><span>排水设施</span></div>
          <div><strong>{{ summary.inletCount }}</strong><span>雨水口</span></div>
          <div><strong class="warn">{{ summary.missingCoordCount }}</strong><span>缺坐标</span></div>
          <div><strong class="warn">{{ summary.neverCleanedCount }}</strong><span>从未清掏</span></div>
        </div>
      </template>
    </aside>

    <!-- 缺资料的点：不占图面，只在下方列出缺什么 -->
    <footer class="missing-bar">
      <div class="missing-group">
        <span class="missing-tag">缺坐标（{{ visibleMissingCoord.length }}）</span>
        <button
          v-for="point in visibleMissingCoord"
          :key="`mc-${point.kind}-${point.id}`"
          class="missing-chip"
          :class="{ active: isSelected(point) }"
          type="button"
          @click="choosePoint(point)"
        >
          {{ point.kind === 'facility' ? '设施' : '雨水口' }} {{ point.code }} · {{ point.road }} · 缺坐标{{ point.lastClean ? '' : '、未清掏' }}
        </button>
        <span v-if="!visibleMissingCoord.length" class="muted-text">当前范围内坐标齐全</span>
      </div>
      <div class="missing-group">
        <span class="missing-tag">从未清掏但有坐标（{{ visibleNeverCleaned.length }}）</span>
        <button
          v-for="point in visibleNeverCleaned"
          :key="`nc-${point.kind}-${point.id}`"
          class="missing-chip"
          :class="{ active: isSelected(point) }"
          type="button"
          @click="choosePoint(point)"
        >
          {{ point.kind === 'facility' ? '设施' : '雨水口' }} {{ point.code }} · {{ point.road }} · 未清掏
        </button>
        <span v-if="!visibleNeverCleaned.length" class="muted-text">当前范围内均有清掏记录</span>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useDrainMapStore, type MapSelection, type MapViewport, type PointKind } from '@/stores/drainMap'

interface MapPoint {
  kind: PointKind
  id: number
  code: string
  name: string | null
  road: string | null
  status: string | null
  coord: { x: number; y: number } | null
  hasCoord: boolean
  lastClean: string | null
  floodCount: number
  pipePath: [number, number][] | null
  crew?: string | null
  facilityCode?: string | null
  missing: string[]
  complaints?: Record<string, string | number | null>[]
}

interface MapOverview {
  roads: { name: string; path: [number, number][] }[]
  points: MapPoint[]
  summary: {
    facilityCount: number
    inletCount: number
    missingCoordCount: number
    neverCleanedCount: number
  }
}

const WORLD = { width: 1000, height: 820 }
const DEFAULT_VIEW: MapViewport = { k: 1, tx: 0, ty: 0 }
const TODAY = new Date('2026-09-25T00:00:00')

const store = useDrainMapStore()
const canvasRef = ref<HTMLElement | null>(null)

const roads = ref<MapOverview['roads']>([])
const points = ref<MapPoint[]>([])
const summary = ref<MapOverview['summary'] | null>(null)
const loading = ref(false)
const loadError = ref('')

const detail = ref<MapPoint | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

const view = ref<MapViewport>({ ...DEFAULT_VIEW })
const dragging = ref(false)
const dragStart = ref<{ x: number; y: number; tx: number; ty: number } | null>(null)
let dragMoved = false

const roadFilter = ref(store.road)
const activeRoad = computed(() => roadFilter.value)

const locatedPoints = computed(() => points.value.filter((point) => point.hasCoord))
function roadMatched(point: MapPoint): boolean {
  return !activeRoad.value || point.road === activeRoad.value
}
const visibleMissingCoord = computed(() => missingCoordPoints.value.filter(roadMatched))
const visibleNeverCleaned = computed(() => neverCleanedLocated.value.filter(roadMatched))
const missingCoordPoints = computed(() => points.value.filter((point) => !point.hasCoord))
const neverCleanedLocated = computed(() =>
  locatedPoints.value.filter((point) => point.lastClean === null),
)
const selectedPipe = computed(() => (detail.value?.kind === 'facility' ? detail.value.pipePath : null))

function roadPath(path: [number, number][]): string {
  return path.map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x} ${y}`).join(' ')
}

function linePoints(path: [number, number][]): string {
  return path.map(([x, y]) => `${x},${y}`).join(' ')
}

function markerShape(point: MapPoint) {
  return point.coord ?? { x: 0, y: 0 }
}

function cleanAgeDays(point: MapPoint): number | null {
  if (!point.lastClean) {
    return null
  }
  const cleanDate = new Date(`${point.lastClean}T00:00:00`)
  return Math.round((TODAY.getTime() - cleanDate.getTime()) / 86_400_000)
}

function cleanFill(point: MapPoint): string {
  const age = cleanAgeDays(point)
  if (age === null) {
    return 'url(#clean-never)'
  }
  if (age <= 30) {
    return 'url(#clean-fresh)'
  }
  if (age <= 90) {
    return 'url(#clean-normal)'
  }
  return 'url(#clean-stale)'
}

function pointStroke(point: MapPoint): string {
  if (!point.lastClean) {
    return '#64748b'
  }
  if (point.status === '堵塞待修') {
    return '#dc2626'
  }
  const age = cleanAgeDays(point)
  if (age === null) {
    return '#64748b'
  }
  if (age <= 30) {
    return '#16a34a'
  }
  if (age <= 90) {
    return '#ca8a04'
  }
  return '#b91c1c'
}

function floodClass(count: number): string {
  if (count >= 5) {
    return 'tick-high'
  }
  if (count >= 3) {
    return 'tick-mid'
  }
  return 'tick-low'
}

function tickLen(n: number): number {
  return 6 + n * 4
}

function pointDimmed(point: MapPoint): boolean {
  if (activeRoad.value && point.road !== activeRoad.value) {
    return true
  }
  return false
}

function isSelected(point: MapPoint): boolean {
  return store.selection?.kind === point.kind && store.selection?.id === point.id
}

function missingLabel(label: string): string {
  return label === '上次清疏' ? '上次清疏（从未清掏）' : label === '上次清掏' ? '上次清掏（从未清掏）' : label
}

function kindOfMissing(label: string): boolean {
  return Boolean(detail.value?.missing.includes(label))
}

async function loadOverview() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await request('/api/drain/map/overview')
    if (!response.ok) {
      throw new Error(`分布视图返回 ${response.status}`)
    }
    const payload = (await response.json()) as MapOverview
    roads.value = payload.roads ?? []
    points.value = payload.points ?? []
    summary.value = payload.summary ?? null
    if (store.selection) {
      await loadDetail(store.selection, { silent: true })
    }
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '分布数据加载失败'
  } finally {
    loading.value = false
  }
}

async function loadDetail(selection: MapSelection, options: { silent?: boolean } = {}) {
  if (!options.silent) {
    detailLoading.value = true
  }
  detailError.value = ''
  try {
    const response = await request(`/api/drain/map/${selection.kind}/${selection.id}`)
    if (!response.ok) {
      throw new Error(`点位明细返回 ${response.status}`)
    }
    detail.value = (await response.json()) as MapPoint
  } catch (error) {
    detail.value = null
    detailError.value = error instanceof Error ? error.message : '点位明细加载失败'
  } finally {
    detailLoading.value = false
  }
}

async function choosePoint(point: MapPoint, fromDrag = false) {
  if (fromDrag && dragMoved) {
    return
  }
  const selection: MapSelection = { kind: point.kind, id: point.id, code: point.code }
  store.select(selection)
  await loadDetail(selection)
  if (point.hasCoord && point.coord) {
    centerOn(point.coord.x, point.coord.y)
  }
}

function clearSelection() {
  store.select(null)
  detail.value = null
}

async function jumpFacility(code: string) {
  const target = points.value.find((point) => point.kind === 'facility' && point.code === code)
  if (target) {
    await choosePoint(target)
    roadFilter.value = ''
    store.setRoad('')
  }
}

function onRoadChange() {
  store.setRoad(roadFilter.value)
  const targetRoads = roadFilter.value
    ? roads.value.filter((road) => road.name === roadFilter.value)
    : roads.value
  fitRoads(targetRoads)
}

// ---- 视野：平移 / 缩放 / 复位 / 恢复 -------------------------------

function fitViewportToPoints(worldPoints: [number, number][], pad = 60) {
  if (!worldPoints.length || !canvasRef.value) {
    view.value = { ...DEFAULT_VIEW }
    return
  }
  const xs = worldPoints.map(([x]) => x)
  const ys = worldPoints.map(([, y]) => y)
  const minX = Math.min(...xs) - pad
  const maxX = Math.max(...xs) + pad
  const minY = Math.min(...ys) - pad
  const maxY = Math.max(...ys) + pad
  const rect = canvasRef.value.getBoundingClientRect()
  const k = Math.min(rect.width / (maxX - minX), rect.height / (maxY - minY), 2.2)
  const tx = (rect.width - k * (minX + maxX)) / 2
  const ty = (rect.height - k * (minY + maxY)) / 2
  view.value = { k, tx, ty }
}

function fitRoads(targetRoads: { path: [number, number][] }[]) {
  const worldPoints = targetRoads.flatMap((road) => road.path)
  fitViewportToPoints(worldPoints.length ? worldPoints : [[0, 0], [WORLD.width, WORLD.height]])
  store.setViewport(view.value)
}

function resetView() {
  roadFilter.value = ''
  store.setRoad('')
  fitViewportToPoints([[0, 0], [WORLD.width, WORLD.height]], 40)
  store.setViewport(view.value)
}

function centerOn(worldX: number, worldY: number) {
  if (!canvasRef.value) {
    return
  }
  const rect = canvasRef.value.getBoundingClientRect()
  view.value = {
    k: Math.max(view.value.k, 1),
    tx: rect.width / 2 - worldX * Math.max(view.value.k, 1),
    ty: rect.height / 2 - worldY * Math.max(view.value.k, 1),
  }
  store.setViewport(view.value)
}

function zoomBy(factor: number) {
  if (!canvasRef.value) {
    return
  }
  const rect = canvasRef.value.getBoundingClientRect()
  zoomAt(rect.width / 2, rect.height / 2, factor)
}

function zoomAt(screenX: number, screenY: number, factor: number) {
  const next = Math.min(Math.max(view.value.k * factor, 0.4), 6)
  const ratio = next / view.value.k
  view.value = {
    k: next,
    tx: screenX - (screenX - view.value.tx) * ratio,
    ty: screenY - (screenY - view.value.ty) * ratio,
  }
  store.setViewport(view.value)
}

function onWheel(event: WheelEvent) {
  zoomAt(event.offsetX, event.offsetY, event.deltaY < 0 ? 1.12 : 0.89)
}

function startPan(event: MouseEvent) {
  if (event.button !== 0) {
    return
  }
  dragging.value = true
  dragMoved = false
  dragStart.value = { x: event.clientX, y: event.clientY, tx: view.value.tx, ty: view.value.ty }
  window.addEventListener('mousemove', onPan)
  window.addEventListener('mouseup', endPan)
}

function onPan(event: MouseEvent) {
  if (!dragStart.value) {
    return
  }
  if (
    Math.abs(event.clientX - dragStart.value.x) > 3 ||
    Math.abs(event.clientY - dragStart.value.y) > 3
  ) {
    dragMoved = true
  }
  view.value = {
    ...view.value,
    tx: dragStart.value.tx + event.clientX - dragStart.value.x,
    ty: dragStart.value.ty + event.clientY - dragStart.value.y,
  }
}

function endPan() {
  dragging.value = false
  dragStart.value = null
  window.removeEventListener('mousemove', onPan)
  window.removeEventListener('mouseup', endPan)
  store.setViewport(view.value)
}

// 管段明细小图：把世界坐标压进 300×120 的画框
const miniTransform = computed(() => {
  const path = detail.value?.pipePath ?? []
  const identity = { scale: 1, offsetX: 0, offsetY: 0 }
  if (!path.length) {
    return identity
  }
  const xs = path.map(([x]) => x)
  const ys = path.map(([, y]) => y)
  const spanX = Math.max(...xs) - Math.min(...xs) || 1
  const spanY = Math.max(...ys) - Math.min(...ys) || 1
  const scale = Math.min(260 / spanX, 90 / spanY)
  return {
    scale,
    offsetX: 20 - Math.min(...xs) * scale,
    offsetY: 15 - Math.min(...ys) * scale,
  }
})

const miniPolylinePoints = computed(() =>
  (detail.value?.pipePath ?? [])
    .map(([x, y]) => `${x * miniTransform.value.scale + miniTransform.value.offsetX},${y * miniTransform.value.scale + miniTransform.value.offsetY}`)
    .join(' '),
)

function miniX(node: [number, number]): number {
  return node[0] * miniTransform.value.scale + miniTransform.value.offsetX
}

function miniY(node: [number, number]): number {
  return node[1] * miniTransform.value.scale + miniTransform.value.offsetY
}

onMounted(async () => {
  await loadOverview()
  if (store.viewport) {
    view.value = { ...store.viewport }
  } else {
    resetView()
  }
})
</script>

<style scoped>
.map-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  grid-template-rows: minmax(420px, 1fr) auto;
  gap: 10px;
  height: calc(100vh - 120px);
  min-height: 560px;
}
.map-canvas {
  position: relative;
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.map-svg {
  width: 100%;
  height: 100%;
  cursor: grab;
  user-select: none;
}
.map-svg.grabbing { cursor: grabbing; }
.road-base {
  fill: none;
  stroke: #e2e8f0;
  stroke-width: 18;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.road-base.dimmed { opacity: 0.35; }
.road-label {
  font-size: 15px;
  font-weight: 600;
  fill: #94a3b8;
  paint-order: stroke;
  stroke: #f8fafc;
  stroke-width: 4;
}
.road-label.dimmed { opacity: 0.4; }
.pipe-line {
  fill: none;
  stroke: #2563eb;
  stroke-width: 3;
  stroke-dasharray: 8 5;
  marker-end: url(#pipe-arrow);
}
.map-point { cursor: pointer; }
.map-point.dimmed { opacity: 0.3; }
.map-point.selected rect,
.map-point.selected circle {
  filter: drop-shadow(0 0 5px rgba(37, 99, 235, 0.9));
}
.point-label {
  font-size: 10px;
  fill: #334155;
  paint-order: stroke;
  stroke: #f8fafc;
  stroke-width: 3;
  pointer-events: none;
}
.never-badge {
  font-size: 9px;
  fill: #b42318;
  paint-order: stroke;
  stroke: #fff;
  stroke-width: 3;
  pointer-events: none;
}
.flood-plus {
  font-size: 9px;
  font-weight: 700;
  pointer-events: none;
  paint-order: stroke;
  stroke: #f8fafc;
  stroke-width: 3;
}
.tick-high { stroke: #dc2626; }
.tick-mid { stroke: #ea580c; }
.tick-low { stroke: #2563eb; }
text.tick-high { fill: #dc2626; }
text.tick-mid { fill: #ea580c; }
text.tick-low { fill: #2563eb; }
dd.tick-high, dd.tick-mid, dd.tick-low { color: #334155; font-weight: 600; }
dd.tick-high { color: #dc2626; }
dd.tick-mid { color: #ea580c; }
dd.tick-low { color: #2563eb; }
.map-toolbar {
  position: absolute;
  top: 10px;
  left: 10px;
  display: flex;
  gap: 6px;
  align-items: center;
}
.road-select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 13px;
  background: #fff;
}
.map-legend {
  position: absolute;
  left: 10px;
  bottom: 10px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  color: #334155;
}
.legend-title { font-weight: 600; margin-bottom: 4px; }
.legend-row { display: flex; align-items: center; gap: 6px; line-height: 18px; }
.map-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 13px;
  color: var(--muted);
  background: rgba(255, 255, 255, 0.9);
  padding: 6px 12px;
  border-radius: 6px;
}
.map-hint.error { color: #b42318; }
.map-hint-inline { margin: 4px 0; font-size: 12px; }
.map-hint-inline.error { color: #b42318; }
.map-detail {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  overflow-y: auto;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.detail-kind {
  display: inline-block;
  font-size: 11px;
  color: #fff;
  background: var(--brand);
  border-radius: 4px;
  padding: 1px 6px;
  margin-right: 6px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 10px;
  margin: 0 0 10px;
}
.detail-grid dt { font-size: 11px; color: var(--muted); }
.detail-grid dd { margin: 2px 0 0; font-size: 13px; }
.detail-grid dd.missing { color: #b42318; }
.missing-box {
  background: #fff7ed;
  border: 1px solid #fdba74;
  color: #9a3412;
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 12px;
  margin-bottom: 10px;
}
.detail-section h4 { margin: 10px 0 6px; font-size: 13px; }
.pipe-chart svg {
  width: 100%;
  height: 120px;
  border: 1px dashed var(--border);
  border-radius: 6px;
  background: #f8fafc;
}
.mini-pipe {
  fill: none;
  stroke: #2563eb;
  stroke-width: 2.5;
}
.mini-note { font-size: 9px; fill: var(--muted); }
.pipe-nodes { margin: 6px 0 0; padding-left: 18px; font-size: 12px; color: #334155; }
.complaint-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.complaint-list li {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 12px;
}
.complaint-top { display: flex; justify-content: space-between; align-items: center; }
.complaint-status {
  font-size: 11px;
  background: #eff6ff;
  color: var(--brand);
  border-radius: 4px;
  padding: 0 6px;
}
.complaint-list p { margin: 4px 0; }
.muted-text { color: var(--muted); font-size: 12px; }
.detail-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 12px;
}
.detail-stats div {
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  display: flex;
  flex-direction: column;
}
.detail-stats strong { font-size: 18px; }
.detail-stats span { font-size: 11px; color: var(--muted); }
.detail-stats .warn { color: #d97706; }
.missing-bar {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
}
.missing-group { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.missing-tag {
  font-size: 12px;
  font-weight: 600;
  color: #9a3412;
  background: #fff7ed;
  border-radius: 4px;
  padding: 2px 6px;
}
.missing-chip {
  border: 1px solid #fed7aa;
  background: #fffaf5;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  cursor: pointer;
  color: #9a3412;
}
.missing-chip.active { border-color: var(--brand); background: #eff6ff; color: var(--brand); }
</style>
