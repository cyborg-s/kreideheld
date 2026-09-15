import { useEffect, useState } from 'react'

import type { RestItem, RestItemForm, UsedNumbersByEmployee } from './types'
import {
  findNextNumber,
  loadRestItems,
  loadUsedNumbers,
  saveRestItems,
  saveUsedNumbers,
} from './storage/localStorage'

export default function App() {
  const [form, setForm] = useState<RestItemForm>({
    employeeCode: 'MA1',
    material: '',
    length: '',
    width: '',
    height: '',
    notes: '',
  })
  const [usedNumbers, setUsedNumbers] = useState<UsedNumbersByEmployee>(loadUsedNumbers)
  const [restItems, setRestItems] = useState<RestItem[]>(loadRestItems)
  const [lastSavedId, setLastSavedId] = useState<number | null>(null)
  const [formError, setFormError] = useState('')

  useEffect(() => {
    saveUsedNumbers(usedNumbers)
  }, [usedNumbers])

  useEffect(() => {
    saveRestItems(restItems)
  }, [restItems])

  const nextChalkId = () => {
    const freeNumber = findNextNumber(form.employeeCode, usedNumbers[form.employeeCode])

    return freeNumber === null
      ? 'ID-Bereich voll - online neuen Bereich zuweisen'
      : `${freeNumber}`
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
    const freeNumber = findNextNumber(form.employeeCode, usedNumbers[form.employeeCode])
    const dimensions = [Number(form.length), Number(form.width), Number(form.height)]

    if (freeNumber === null) {
      setFormError('Der ID-Bereich ist voll. Bitte gehe online.')
      return
    }

    if (
      form.material.trim() === '' ||
      dimensions.some((dimension) => !Number.isInteger(dimension) || dimension <= 0)
    ) {
      setFormError('Material und positive Maße in Millimetern sind erforderlich.')
      return
    }

    const restItem: RestItem = {
      id: crypto.randomUUID(),
      chalkId: freeNumber,
      employeeCode: form.employeeCode,
      material: form.material.trim(),
      length: dimensions[0],
      width: dimensions[1],
      height: dimensions[2],
      notes: form.notes.trim(),
    }

    setUsedNumbers((current) => ({
      ...current,
      [form.employeeCode]: [...current[form.employeeCode], freeNumber],
    }))
    setRestItems((current) => [...current, restItem])
    setLastSavedId(freeNumber)
    setFormError('')
    setForm((current) => ({
      ...current,
      material: '',
      length: '',
      width: '',
      height: '',
      notes: '',
    }))

    console.log('Gespeichert:', {
      ...form,
      chalkId: freeNumber,
    })
  }

  return (
    <main style={{ padding: '32px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Neues Reststück</h1>
      {lastSavedId !== null && <p>Gespeichert mit Kreide-ID {lastSavedId}</p>}
      {formError !== '' && <p>{formError}</p>}

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

      <section>
        <h2>Gespeicherte Reststücke</h2>
        {restItems.length === 0 ? (
          <p>Noch keine Reststücke gespeichert.</p>
        ) : (
          <ul>
            {restItems.map((item) => (
              <li key={item.id}>
                {item.employeeCode}-{item.chalkId}: {item.material} ({item.length} x {item.width} x {item.height} mm)
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}