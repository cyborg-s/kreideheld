import type {
  EmployeeCode,
  NumberRange,
  RestItem,
  UsedNumbersByEmployee,
} from '../types'

export const employeeRanges: Record<EmployeeCode, NumberRange> = {
  MA1: { min: 1000, max: 1999 },
  MA2: { min: 2000, max: 2999 },
  MA3: { min: 3000, max: 3999 },
}

const defaultUsedNumbers: UsedNumbersByEmployee = {
  MA1: [1000, 1001, 1002, 1005],
  MA2: [2000, 2001, 2003],
  MA3: [3000, 3001, 3002],
}

const usedNumbersStorageKey = 'kreideheld.usedNumbers'
const restItemsStorageKey = 'kreideheld.restItems'

function isEmployeeCode(value: unknown): value is EmployeeCode {
  return value === 'MA1' || value === 'MA2' || value === 'MA3'
}

function isRestItem(value: unknown): value is RestItem {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  const item = value as Record<string, unknown>
  return (
    typeof item.id === 'string' &&
    typeof item.chalkId === 'number' &&
    isEmployeeCode(item.employeeCode) &&
    typeof item.material === 'string' &&
    typeof item.length === 'number' &&
    typeof item.width === 'number' &&
    typeof item.height === 'number' &&
    typeof item.notes === 'string'
  )
}

export function loadRestItems(): RestItem[] {
  const storedItems = localStorage.getItem(restItemsStorageKey)

  if (storedItems === null) {
    return []
  }

  try {
    const parsedItems: unknown = JSON.parse(storedItems)
    return Array.isArray(parsedItems) ? parsedItems.filter(isRestItem) : []
  } catch {
    return []
  }
}

export function saveRestItems(restItems: RestItem[]) {
  localStorage.setItem(restItemsStorageKey, JSON.stringify(restItems))
}

export function loadUsedNumbers(): UsedNumbersByEmployee {
  const storedNumbers = localStorage.getItem(usedNumbersStorageKey)

  if (storedNumbers === null) {
    return defaultUsedNumbers
  }

  try {
    const parsedNumbers = JSON.parse(storedNumbers) as Partial<Record<EmployeeCode, unknown>>
    const employeeCodes: EmployeeCode[] = ['MA1', 'MA2', 'MA3']

    if (!employeeCodes.every((employeeCode) => Array.isArray(parsedNumbers[employeeCode]))) {
      return defaultUsedNumbers
    }

    const getNumbers = (employeeCode: EmployeeCode) => {
      const values = parsedNumbers[employeeCode]
      return Array.isArray(values)
        ? values.filter((value): value is number => typeof value === 'number')
        : []
    }

    return {
      MA1: getNumbers('MA1'),
      MA2: getNumbers('MA2'),
      MA3: getNumbers('MA3'),
    }
  } catch {
    return defaultUsedNumbers
  }
}

export function saveUsedNumbers(usedNumbers: UsedNumbersByEmployee) {
  localStorage.setItem(usedNumbersStorageKey, JSON.stringify(usedNumbers))
}

export function findNextNumber(
  employeeCode: EmployeeCode,
  usedNumbers: number[],
): number | null {
  const range = employeeRanges[employeeCode]

  for (let number = range.min; number <= range.max; number += 1) {
    if (!usedNumbers.includes(number)) {
      return number
    }
  }

  return null
}
