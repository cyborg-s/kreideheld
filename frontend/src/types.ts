export type EmployeeCode = 'MA1' | 'MA2' | 'MA3'

export type RestItemForm = {
  employeeCode: EmployeeCode
  material: string
  length: string
  width: string
  height: string
  notes: string
}

export type RestItem = {
  id: string
  chalkId: number
  employeeCode: EmployeeCode
  material: string
  length: number
  width: number
  height: number
  notes: string
}

export type NumberRange = {
  min: number
  max: number
}

export type UsedNumbersByEmployee = Record<EmployeeCode, number[]>
