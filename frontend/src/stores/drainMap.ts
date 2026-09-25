import { defineStore } from 'pinia'

/** 分布视图点位类型：facility=排水设施，inlet=雨水口。 */
export type PointKind = 'facility' | 'inlet'

export interface MapSelection {
  kind: PointKind
  id: number
  code: string
}

/** 屏幕坐标换算：screen = world * k + translate。 */
export interface MapViewport {
  k: number
  tx: number
  ty: number
}

const STORAGE_KEY = 'drain-map-state'

interface PersistedState {
  viewport: MapViewport
  selection: MapSelection | null
  road: string
}

function loadState(): PersistedState | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as Partial<PersistedState>
    if (!parsed.viewport || typeof parsed.viewport.k !== 'number') {
      return null
    }
    return {
      viewport: parsed.viewport,
      selection: parsed.selection ?? null,
      road: typeof parsed.road === 'string' ? parsed.road : '',
    }
  } catch {
    return null
  }
}

/**
 * 排水分布视图的共享状态：地图与台账通过它同步高亮，
 * 视野、选中项与道路筛选写入 localStorage，重新打开视图时恢复。
 */
export const useDrainMapStore = defineStore('drainMap', {
  state: () => {
    const restored = loadState()
    return {
      viewport: restored?.viewport ?? null,
      selection: restored?.selection ?? null,
      road: restored?.road ?? '',
    }
  },
  actions: {
    setViewport(viewport: MapViewport) {
      this.viewport = { ...viewport }
      this.persist()
    },
    select(selection: MapSelection | null) {
      this.selection = selection ? { ...selection } : null
      this.persist()
    },
    setRoad(road: string) {
      this.road = road
      this.persist()
    },
    persist() {
      try {
        window.localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ viewport: this.viewport, selection: this.selection, road: this.road }),
        )
      } catch {
        // 隐私模式等场景写不进去就算了，不影响当次浏览
      }
    },
  },
})
