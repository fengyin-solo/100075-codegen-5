import { defineStore } from 'pinia'

/** 分布视图的视野：SVG viewBox 的位置与尺寸。 */
export interface MapViewState {
  x: number
  y: number
  w: number
  h: number
}

/**
 * 排水设施分布视图的界面状态。
 * 视野、选中项与道路筛选都放在这里，切走再打开视图时原样恢复。
 */
export const useDrainMapStore = defineStore('drainMap', {
  state: () => ({
    view: null as MapViewState | null,
    selectedId: null as number | null,
    roadFilter: '',
    tab: 'ledger' as 'ledger' | 'map',
  }),
  actions: {
    setView(view: MapViewState) {
      this.view = view
    },
    select(id: number | null) {
      this.selectedId = id
    },
    setRoadFilter(name: string) {
      this.roadFilter = name
    },
    setTab(tab: 'ledger' | 'map') {
      this.tab = tab
    },
  },
})
