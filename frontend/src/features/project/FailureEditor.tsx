import { useState } from "react";

export function FailureEditor() {
  const [items, setItems] = useState([
    { satellite: "S06", from: "06:00", to: "24:00" },
  ]);
  return (
    <div className="failure-editor">
      <div className="section-heading">
        <div><h3>Отказы</h3><p>Демонстрационная форма без отправки на backend.</p></div>
        <button
          className="secondary-button"
          onClick={() =>
            setItems((current) => [
              ...current,
              { satellite: `S${String(current.length + 12).padStart(2, "0")}`, from: "12:00", to: "18:00" },
            ])
          }
        >
          + Добавить
        </button>
      </div>
      {items.map((item, index) => (
        <div className="failure-row" key={index}>
          <input
            value={item.satellite}
            onChange={(event) =>
              setItems((current) =>
                current.map((value, itemIndex) =>
                  itemIndex === index ? { ...value, satellite: event.target.value } : value,
                ),
              )
            }
          />
          <input value={item.from} readOnly />
          <span>→</span>
          <input value={item.to} readOnly />
          <button onClick={() => setItems((current) => current.filter((_, itemIndex) => itemIndex !== index))}>×</button>
        </div>
      ))}
    </div>
  );
}
