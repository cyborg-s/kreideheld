import { useState } from 'react'

type RestItemForm = {
  employeeCode: string
  material: string
  length: string
  width: string
  height: string
  notes: string
}

export default function App() {
  const [form, setForm] = useState<RestItemForm>({
    employeeCode: 'MA1',
    material: '',
    length: '',
    width: '',
    height: '',
    notes: '',
  })

  const employeeRange = {
    MA1: { min: 1000, max: 1999 },
    MA2: { min: 2000, max: 2999 },
    MA3: { min: 3000, max: 3999 },
  }

  const usedNumbersByEmployee: Record<string, number[]> = {
    MA1: [1000, 1001, 1002, 1005],
    MA2: [2000, 2001, 2003],
    MA3: [3000, 3001, 3002],
  }

  const nextChalkId = () => {
    const range = employeeRange[form.employeeCode as keyof typeof employeeRange]
    const usedNumbers = usedNumbersByEmployee[form.employeeCode]
    const freeNumber = Array.from({ length: range.max - range.min + 1 }, (_, index) => range.min + index).find(
      (number) => !usedNumbers.includes(number)
    )

    return freeNumber ? `${freeNumber}` : `ID-Bereich-voll gehe online um weitere IDs zu generieren`
  }

  const handleChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = event.target
    setForm((current) => ({
      ...current,
      [name]: value,
    }))
  }

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    console.log('Gespeichert:', {
      ...form,
      chalkId: nextChalkId(),
    })
  }

  return (
    <main style={{ padding: '32px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Neues Reststück</h1>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '16px' }}>
          <label>Mitarbeiter</label>
          <select name="employeeCode" value={form.employeeCode} onChange={handleChange}>
            <option value="MA1">MA1</option>
            <option value="MA2">MA2</option>
            <option value="MA3">MA3</option>
          </select>
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label>Kreide-ID</label>
          <input value={nextChalkId()} readOnly />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label>Material</label>
          <input name="material" value={form.material} onChange={handleChange} />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label>Länge in mm</label>
          <input name="length" value={form.length} onChange={handleChange} />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label>Breite in mm</label>
          <input name="width" value={form.width} onChange={handleChange} />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label>Höhe in mm</label>
          <input name="height" value={form.height} onChange={handleChange} />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label>Notiz</label>
          <textarea name="notes" value={form.notes} onChange={handleChange} />
        </div>

        <button type="submit">Speichern</button>
      </form>
    </main>
  )
}