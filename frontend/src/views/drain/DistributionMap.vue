<template>
  <div class="map-view">
    <div class="map-toolbar">
      <label class="map-filter">
        <span>所在道路</span>
        <select :value="store.roadFilter" @change="onRoadFilter">
          <option value="">全部道路</option>
          <option v-for="road in roads" :key="road.name" :value="road.name">{{ road.name }}</option>
        </select>
      </label>
      <div class="map-zoom">
        <button class="btn" type="button" @click="zoom(0.8)">放大</button>
        <button class="btn" type="button" @click="zoom(1.25)">缩小</button>
        <button class="btn ghost" type="button" @click="resetView">重置视野</button>
      </div>
      <span class="map-hint">拖动平移、滚轮缩放，点击设施点查看管线走向与关联诉求</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </div>

    <div class="map-legend">
      <span class="legend-item"><i class="legend-shape circle"></i>排水设施</span>
      <span class="legend-item"><i class="legend-shape square"></i>雨水口</span>
      <span class="legend-item"><i class="legend-shape recent"></i>90 天内清掏</span>
      <span class="legend-item"><i class="legend-shape mid"></i>180 天内清掏</span>
      <span class="legend-item"><i class="legend-shape stale"></i>180 天以上未清掏</span>
      <span class="legend-item"><i class="legend-shape never"></i>尚未清掏</span>
      <span class="legend-item">点越大、角标数字越大，历史积水次数越多</span>
    </div>

    <div class="map-body">
      <div class="map-canvas">
        <svg
          ref="svgEl"
          :viewBox="viewBoxText"
          @wheel.prevent="onWheel"
          @pointerdown="onPanStart"
          @pointermove="onPanMove"
          @pointerup="onPanEnd"
          @pointerleave="onPanEnd"
        >
          <g
            v-for="road in roads"
            :key="road.name"
            :class="{ dimmed: store.roadFilter && store.roadFilter !== road.name }"
          >
            <polyline v-if="road.path.length" :points="roadPoints(road)" class="road-line" />
            <text v-if="road.path.length" :x="road.path[0][0]" :y="road.path[0][1] - 16" class="road-name">
              {{ road.name }}
            </text>
          </g>
          <g
            v-for="f in plotted"
            :key="f.id"
            class="facility"
            :class="[cleanClass(f), { selected: f.id === store.selectedId }]"
            @pointerdown.stop
            @click="select(f.id)"
          >
            <title>{{ tooltip(f) }}</title>
            <rect
              v-if="f.设施类型 === '雨水口'"
              :x="f.坐标![0] - size(f)"
              :y="f.坐标![1] - size(f)"
              :width="size(f) * 2"
              :height="size(f) * 2"
              class="facility-shape"
            />
            <circle v-else :cx="f.坐标![0]" :cy="f.坐标![1]" :r="size(f)" class="facility-shape" />
            <text v-if="f.积水次数 > 0" :x="f.坐标![0] + size(f) + 4" :y="f.坐标![1] - size(f) - 4" class="flood-badge">
              {{ f.积水次数 }}
            </text>
            <text :x="f.坐标![0]" :y="f.坐标![1] + size(f) + 16" class="facility-label">{{ f.设施编号 }}</text>
          </g>
        </svg>
        <p v-if="!plotted.length" class="map-empty">当前筛选下没有可上图的设施点位</p>
      </div>

      <aside v-if="store.selectedId !== null" class="map-detail">
        <header class="detail-head">
          <strong>{{ entryText('设施编号') || '设施详情' }}</strong>
          <button class="link" type="button" @click="select(null)">关闭</button>
        </header>
        <p v-if="profileError" class="error-text">{{ profileError }}</p>
        <template v-if="profile">
          <dl class="detail-grid">
            <div><dt>设施类型</dt><dd>{{ entryText('设施类型') || '—' }}</dd></div>
            <div><dt>所在道路</dt><dd>{{ entryText('所在道路') || '—' }}</dd></div>
            <div><dt>设施状态</dt><dd>{{ entryText('status') || '—' }}</dd></div>
            <div><dt>上次清掏</dt><dd>{{ entryText('上次清疏日') || '未清掏' }}</dd></div>
            <div><dt>历史积水</dt><dd>{{ floodCount }} 次</dd></div>
          </dl>
          <p v-if="profile.缺失.length" class="missing-line">
            该点缺失：
            <em v-for="m in profile.缺失" :key="m" class="missing-tag">{{ m }}</em>
          </p>
          <section class="detail-section">
            <h3>排水管走向</h3>
            <svg v-if="profile.pipes.length" :viewBox="pipeViewBox" class="pipe-map">
              <defs>
                <marker id="pipe-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                  <path d="M0,0 L8,4 L0,8 z" class="pipe-arrow" />
                </marker>
              </defs>
              <polyline
                v-for="pipe in profile.pipes"
                :key="pipe.管段编号"
                :points="pipePoints(pipe)"
                class="pipe-line"
                marker-end="url(#pipe-arrow)"
              />
              <circle v-if="entryCoord" :cx="entryCoord[0]" :cy="entryCoord[1]" r="7" class="pipe-origin" />
            </svg>
            <p v-else class="detail-empty">暂无管线走向记录</p>
            <ul v-if="profile.pipes.length" class="pipe-list">
              <li v-for="pipe in profile.pipes" :key="pipe.管段编号">
                {{ pipe.管段编号 }} · {{ pipe.管径 }} · {{ pipe.流向 }}
              </li>
            </ul>
          </section>
          <section class="detail-section">
            <h3>关联诉求记录</h3>
            <ul v-if="profile.complaints.length" class="complaint-list">
              <li v-for="c in profile.complaints" :key="c.id">
                <header>
                  <strong>{{ c.诉求编号 }}</strong>
                  <span class="complaint-status">{{ c.status }}</span>
                </header>
                <p>{{ c.诉求内容 }}</p>
              </li>
            </ul>
            <p v-else class="detail-empty">暂无关联诉求</p>
          </section>
        </template>
        <p v-else-if="!profileError" class="detail-empty">详情加载中…</p>
      </aside>
    </div>

    <div v-if="unmapped.length" class="map-unmapped">
      <span class="unmapped-title">未上图设施（缺少坐标，不影响其他点位）：</span>
      <button
        v-for="f in unmapped"
        :key="f.id"
        class="chip"
        :class="{ selected: f.id === store.selectedId }"
        type="button"
        @click="select(f.id)"
      >
        {{ f.设施编号 }} · {{ f.设施类型 }}
        <em v-for="m in f.缺失" :key="m" class="missing-tag">{{ m }}</em>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { fetchJson } from '@/api/client'
import { useDrainMapStore, type MapViewState } from '@/stores/drainMap'

interface FacilityPoint {
  id: number
  设施编号: string
  设施类型: string
  所在道路: string
  status: string
  坐标: [number, number] | null
  上次清疏日: string | null
  积水次数: number
  缺失: string[]
}

interface RoadLine {
  name: string
  path: [number, number][]
}

interface MapPayload {
  canvas: { width: number; height: number }
  roads: RoadLine[]
  facilities: FacilityPoint[]
}

interface PipeSegment {
  管段编号: string
  走向: [number, number][]
  管径: string
  流向: string
}

interface ComplaintRow {
  id: number
  诉求编号: string
  诉求内容: string
  status: string
}

interface Profile {
  entry: Record<string, unknown>
  pipes: PipeSegment[]
  complaints: ComplaintRow[]
  缺失: string[]
}

const MIN_VIEW_W = 120
const MAX_VIEW_W = 3600

const store = useDrainMapStore()

const canvas = ref({ width: 1200, height: 720 })
const roads = ref<RoadLine[]>([])
const facilities = ref<FacilityPoint[]>([])
const errorMessage = ref('')

const aspect = ref(0.6)
const view = ref<MapViewState>(
  store.view ? { ...store.view } : { x: 0, y: 0, w: canvas.value.width, h: canvas.value.height },
)
const svgEl = ref<SVGSVGElement | null>(null)

const profile = ref<Profile | null>(null)
const profileError = ref('')

const viewBoxText = computed(() => `${view.value.x} ${view.value.y} ${view.value.w} ${view.value.h}`)

const plotted = computed(() =>
  facilities.value.filter(
    (f) => f.坐标 && (!store.roadFilter || f.所在道路 === store.roadFilter),
  ),
)

const unmapped = computed(() =>
  facilities.value.filter(
    (f) => f.缺失.includes('缺坐标') && (!store.roadFilter || f.所在道路 === store.roadFilter),
  ),
)

const entryCoord = computed<[number, number] | null>(() => {
  const coord = profile.value?.entry?.['坐标']
  return Array.isArray(coord) && coord.length === 2 ? [Number(coord[0]), Number(coord[1])] : null
})

const floodCount = computed(() => Number(profile.value?.entry?.['积水次数'] ?? 0))

const pipeViewBox = computed(() => {
  const pts: [number, number][] = []
  for (const pipe of profile.value?.pipes ?? []) {
    pts.push(...pipe.走向)
  }
  if (entryCoord.value) {
    pts.push(entryCoord.value)
  }
  if (!pts.length) {
    return '0 0 100 60'
  }
  const xs = pts.map((p) => p[0])
  const ys = pts.map((p) => p[1])
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const w = Math.max(maxX - minX, 1)
  const h = Math.max(maxY - minY, 1)
  const padX = w * 0.25 + 12
  const padY = h * 0.25 + 12
  return `${minX - padX} ${minY - padY} ${w + padX * 2} ${h + padY * 2}`
})

function roadPoints(road: RoadLine): string {
  return road.path.map((p) => p.join(',')).join(' ')
}

function pipePoints(pipe: PipeSegment): string {
  return pipe.走向.map((p) => p.join(',')).join(' ')
}

function cleanClass(f: FacilityPoint): string {
  if (!f.上次清疏日) {
    return 'never'
  }
  const time = new Date(f.上次清疏日).getTime()
  if (Number.isNaN(time)) {
    return 'stale'
  }
  const days = (Date.now() - time) / 86400000
  if (days <= 90) {
    return 'recent'
  }
  return days <= 180 ? 'mid' : 'stale'
}

function size(f: FacilityPoint): number {
  return 7 + Math.min(f.积水次数, 5) * 1.8
}

function tooltip(f: FacilityPoint): string {
  const missing = f.缺失.length ? `｜缺失：${f.缺失.join('、')}` : ''
  return `${f.设施编号}｜${f.设施类型}｜上次清掏：${f.上次清疏日 ?? '未清掏'}｜历史积水 ${f.积水次数} 次${missing}`
}

function entryText(key: string): string {
  const value = profile.value?.entry?.[key]
  return value === null || value === undefined || value === '' ? '' : String(value)
}

function select(id: number | null) {
  store.select(id)
}

function persistView() {
  store.setView({ ...view.value })
}

function clampView(w: number): number {
  return Math.min(Math.max(w, MIN_VIEW_W), MAX_VIEW_W)
}

function zoom(factor: number) {
  const cx = view.value.x + view.value.w / 2
  const cy = view.value.y + view.value.h / 2
  const w = clampView(view.value.w * factor)
  const h = w * aspect.value
  view.value = { x: cx - w / 2, y: cy - h / 2, w, h }
  persistView()
}

function resetView() {
  view.value = { x: 0, y: 0, w: canvas.value.width, h: canvas.value.height }
  persistView()
}

function onWheel(event: WheelEvent) {
  const svg = svgEl.value
  if (!svg) {
    return
  }
  const rect = svg.getBoundingClientRect()
  const fx = (event.clientX - rect.left) / rect.width
  const fy = (event.clientY - rect.top) / rect.height
  const factor = event.deltaY < 0 ? 0.85 : 1.18
  const w = clampView(view.value.w * factor)
  const h = w * aspect.value
  const px = view.value.x + fx * view.value.w
  const py = view.value.y + fy * view.value.h
  view.value = { x: px - fx * w, y: py - fy * h, w, h }
  persistView()
}

let panState: { px: number; py: number; start: MapViewState } | null = null

function onPanStart(event: PointerEvent) {
  panState = { px: event.clientX, py: event.clientY, start: { ...view.value } }
  svgEl.value?.setPointerCapture(event.pointerId)
}

function onPanMove(event: PointerEvent) {
  const svg = svgEl.value
  if (!panState || !svg) {
    return
  }
  const rect = svg.getBoundingClientRect()
  const dx = ((event.clientX - panState.px) / rect.width) * panState.start.w
  const dy = ((event.clientY - panState.py) / rect.height) * panState.start.h
  view.value = { ...panState.start, x: panState.start.x - dx, y: panState.start.y - dy }
}

function onPanEnd() {
  if (panState) {
    panState = null
    persistView()
  }
}

function onRoadFilter(event: Event) {
  store.setRoadFilter((event.target as HTMLSelectElement).value)
}

async function load() {
  errorMessage.value = ''
  try {
    const payload = await fetchJson<MapPayload>('/api/drain/map')
    canvas.value = payload.canvas
    roads.value = payload.roads ?? []
    facilities.value = payload.facilities ?? []
    aspect.value = payload.canvas.height / payload.canvas.width || 0.6
    if (!store.view) {
      resetView()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '分布视图数据读取失败'
  }
}

watch(
  () => store.selectedId,
  async (id) => {
    profile.value = null
    profileError.value = ''
    if (id === null) {
      return
    }
    try {
      profile.value = await fetchJson<Profile>(`/api/drain/${id}/profile`)
    } catch (error) {
      profileError.value = error instanceof Error ? error.message : '设施详情读取失败'
    }
  },
  { immediate: true },
)

onMounted(load)
</script>

<style scoped>
.map-view { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.map-toolbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px; }
.map-filter span { font-size: 12px; color: var(--muted); margin-right: 6px; }
.map-filter select { border: 1px solid var(--border); border-radius: 6px; padding: 5px 8px; font-size: 13px; }
.map-zoom { display: flex; gap: 6px; }
.map-hint { font-size: 12px; color: var(--muted); }
.map-legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: var(--muted); margin-bottom: 10px; }
.legend-item { display: inline-flex; align-items: center; gap: 5px; }
.legend-shape { width: 12px; height: 12px; display: inline-block; }
.legend-shape.circle { border-radius: 50%; background: #2da44e; }
.legend-shape.square { background: #2da44e; }
.legend-shape.recent { border-radius: 50%; background: #2da44e; }
.legend-shape.mid { border-radius: 50%; background: #bf8700; }
.legend-shape.stale { border-radius: 50%; background: #cf222e; }
.legend-shape.never { border-radius: 50%; background: #fff; border: 2px dashed #94a3b8; }
.map-body { display: flex; gap: 12px; align-items: stretch; }
.map-canvas { flex: 1; min-width: 0; position: relative; border: 1px solid var(--border); border-radius: 6px; background: #f8fafc; }
.map-canvas svg { display: block; width: 100%; height: 420px; touch-action: none; cursor: grab; }
.map-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 13px; pointer-events: none; }
.road-line { fill: none; stroke: #94a3b8; stroke-width: 3; vector-effect: non-scaling-stroke; }
.road-name { font-size: 15px; fill: #475569; font-weight: 600; }
.dimmed { opacity: 0.2; }
.facility { cursor: pointer; }
.facility-shape { stroke-width: 2; vector-effect: non-scaling-stroke; }
.facility.recent .facility-shape { fill: #2da44e; stroke: #1a7f37; }
.facility.mid .facility-shape { fill: #bf8700; stroke: #9a6b00; }
.facility.stale .facility-shape { fill: #cf222e; stroke: #a40e26; }
.facility.never .facility-shape { fill: #fff; stroke: #94a3b8; stroke-dasharray: 4 3; }
.facility:hover .facility-shape { stroke: #1f6feb; }
.facility.selected .facility-shape { stroke: #1f6feb; stroke-width: 3.5; }
.facility-label { font-size: 12px; fill: #334155; text-anchor: middle; }
.flood-badge { font-size: 13px; font-weight: 700; fill: #b42318; paint-order: stroke; stroke: #fff; stroke-width: 3px; }
.map-detail { width: 320px; flex-shrink: 0; border: 1px solid var(--border); border-radius: 6px; padding: 12px; background: #fff; overflow-y: auto; max-height: 460px; }
.detail-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 0 0 8px; }
.detail-grid dt { font-size: 12px; color: var(--muted); }
.detail-grid dd { margin: 2px 0 0; font-size: 13px; }
.missing-line { font-size: 12px; color: #b42318; margin: 4px 0 8px; }
.missing-tag { font-style: normal; background: #fef3c7; color: #92400e; border-radius: 4px; padding: 1px 6px; margin-left: 4px; font-size: 12px; }
.detail-section { border-top: 1px solid var(--border); padding-top: 8px; margin-top: 8px; }
.detail-section h3 { font-size: 13px; margin: 0 0 6px; }
.pipe-map { width: 100%; height: 140px; background: #f8fafc; border: 1px solid var(--border); border-radius: 6px; }
.pipe-line { fill: none; stroke: #1f6feb; stroke-width: 2.5; vector-effect: non-scaling-stroke; }
.pipe-arrow { fill: #1f6feb; }
.pipe-origin { fill: #fff; stroke: #1f6feb; stroke-width: 2.5; vector-effect: non-scaling-stroke; }
.pipe-list { margin: 6px 0 0; padding-left: 16px; font-size: 12px; color: var(--muted); }
.complaint-list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; }
.complaint-list li { border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; font-size: 12px; }
.complaint-list header { display: flex; justify-content: space-between; align-items: center; }
.complaint-list p { margin: 4px 0 0; color: var(--muted); }
.complaint-status { font-size: 12px; color: var(--brand); }
.detail-empty { font-size: 12px; color: var(--muted); }
.map-unmapped { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; font-size: 12px; }
.unmapped-title { color: var(--muted); }
.chip { border: 1px solid var(--border); background: #fff; border-radius: 14px; padding: 4px 10px; font-size: 12px; cursor: pointer; }
.chip.selected { border-color: var(--brand); color: var(--brand); }
</style>
