<template>
  <section class="page" data-module="drain">
    <header class="page-head">
      <div>
        <h2>排水设施管理</h2>
        <p class="page-desc">维护排水设施，围绕设施编号、设施类型、所在道路、检查井数量做登记、筛选与状态流转；分布视图按道路铺排排水设施与雨水口。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记排水设施</button>
        <button class="btn" type="button" @click="exportRows">导出排水设施清单</button>
      </div>
    </header>

    <div class="tab-bar">
      <button
        class="tab"
        :class="{ active: activeTab === 'ledger' }"
        type="button"
        @click="switchTab('ledger')"
      >台账列表</button>
      <button
        class="tab"
        :class="{ active: activeTab === 'map' }"
        type="button"
        @click="switchTab('map')"
      >分布视图</button>
    </div>

    <template v-if="activeTab === 'ledger'">
      <div class="stat-row">
        <article v-for="item in stats" :key="item.label" class="stat-card">
          <span class="stat-label">{{ item.label }}</span>
          <strong class="stat-value">{{ item.value }}</strong>
        </article>
      </div>

      <div v-if="mapSelection" class="sync-banner" :class="mapSelection.kind">
        <template v-if="mapSelection.kind === 'facility'">
          分布视图已选中排水设施 <strong>{{ mapSelection.code }}</strong>，对应行已高亮。
          <button class="link" type="button" @click="switchTab('map')">回到分布视图</button>
        </template>
        <template v-else>
          分布视图选中的是雨水口 <strong>{{ mapSelection.code }}</strong>（雨水口不在排水设施台账内登记），
          <button class="link" type="button" @click="switchTab('map')">回到分布视图</button>
          或<button class="link" type="button" @click="clearSelection">清除选中</button>。
        </template>
      </div>

      <form class="filter-bar" @submit.prevent="reload">
        <label v-for="field in filterFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="filters[field]" :placeholder="`按${field}检索`" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table drain-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="String(row.id)"
            :ref="setRowRef(row)"
            :class="{ 'row-selected': isFacilitySelected(row), 'row-pending': !isFacilitySelected(row) && mapSelection?.kind === 'facility' }"
            @click="selectFacility(row)"
          >
            <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
            <td class="row-actions" @click.stop>
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 1" class="empty-state">暂无排水设施数据，可先登记排水设施</td>
          </tr>
        </tbody>
      </table>

      <footer class="page-foot">
        <span>共 {{ total }} 条排水设施记录</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <DrainMapView v-else-if="activeTab === 'map'" />
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, type ComponentPublicInstance } from 'vue'

import { request } from '@/api/client'
import { useDrainMapStore } from '@/stores/drainMap'
import DrainMapView from './MapView.vue'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/drain'
const columns = ["设施编号", "设施类型", "所在道路", "检查井数量", "上次清疏日", "下次清疏日", "责任班组", "设施状态"]
const actions = ["安排清疏", "确认正常", "停用设施"]
const statuses = ["待清疏", "正常使用", "堵塞待修", "已停用"]
const stats = [{"label": "在册排水设施", "value": 0}, {"label": "待清疏设施", "value": 0}, {"label": "堵塞待修", "value": 0}]

const mapStore = useDrainMapStore()
const activeTab = ref<'ledger' | 'map'>('ledger')
const rowRefs = new Map<number, HTMLElement>()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const mapSelection = computed(() => mapStore.selection)

function switchTab(tab: 'ledger' | 'map') {
  activeTab.value = tab
  if (tab === 'ledger') {
    void nextTick(scrollToSelected)
  }
}

function setRowRef(row: Row) {
  return (el: Element | ComponentPublicInstance | null) => {
    if (el instanceof HTMLElement) {
      rowRefs.set(Number(row.id), el)
    } else {
      rowRefs.delete(Number(row.id))
    }
  }
}

function isFacilitySelected(row: Row): boolean {
  return mapStore.selection?.kind === 'facility' && mapStore.selection.id === Number(row.id)
}

function selectFacility(row: Row) {
  const code = String(row['设施编号'] ?? '')
  mapStore.select({ kind: 'facility', id: Number(row.id), code })
}

function clearSelection() {
  mapStore.select(null)
}

function scrollToSelected() {
  const selected = mapStore.selection
  if (!selected || selected.kind !== 'facility') {
    return
  }
  const el = rowRefs.get(selected.id)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '排水设施登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('排水设施动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '排水设施操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('排水设施列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await nextTick(scrollToSelected)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '排水设施列表读取失败'
  }
}

onMounted(() => {
  void reload()
  if (mapStore.selection) {
    void nextTick(scrollToSelected)
  }
})
</script>

<style scoped>
.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.tab {
  border: none;
  background: none;
  padding: 8px 16px;
  font-size: 14px;
  color: var(--muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.tab.active {
  color: var(--brand);
  border-bottom-color: var(--brand);
  font-weight: 600;
}
.sync-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e40af;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  margin-bottom: 10px;
}
.sync-banner.inlet {
  background: #f0fdf4;
  border-color: #bbf7d0;
  color: #166534;
}
.drain-table tr { cursor: pointer; }
.drain-table tr.row-selected {
  background: #dbeafe;
  box-shadow: inset 3px 0 0 var(--brand);
}
.drain-table tr.row-pending { opacity: 0.55; }
</style>
