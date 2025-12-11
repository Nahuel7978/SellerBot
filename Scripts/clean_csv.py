import pandas as pd
import numpy as np


def process_inventory_csv(input_file: str, output_file: str) -> None:
    """
    Procesa un archivo CSV de inventario aplicando transformaciones específicas.
    
    Args:
        input_file: Ruta del archivo CSV de entrada
        output_file: Ruta del archivo CSV de salida
    """
    df = pd.read_csv(input_file)
    
    df = df.drop(columns=['ID'])
    
    df['name'] = (
        df['TIPO_PRENDA'].str.lower() + '_' + 
        df['TALLA'].str.lower() + '_' + 
        df['COLOR'].str.lower()
    )
    
    df = df.drop(columns=['TIPO_PRENDA', 'TALLA', 'COLOR'])
    
    df = df.rename(columns={
        'CATEGORÍA': 'category',
        'CANTIDAD_DISPONIBLE': 'stock',
        'PRECIO_50_U': 'price_fivety_units',
        'PRECIO_100_U': 'price_one_hundred_units',
        'PRECIO_200_U': 'price_two_hundred_units',
        'DESCRIPCIÓN': 'descripcion'
    })
    
    df['category'] = df['category'].str.lower()

    df['DISPONIBLE'] = df['DISPONIBLE'].fillna('')
    df = df[~df['DISPONIBLE'].str.upper().isin(['NO', 'N', ''])]
    
    price_cols = ['price_fivety_units', 'price_one_hundred_units', 'price_two_hundred_units']
    df = df[~(df[price_cols] < 0).any(axis=1)]
    
    df = df.drop(columns=['DISPONIBLE'])
    
    cols = ['name', 'descripcion'] + [col for col in df.columns if col not in ['name', 'descripcion']]
    df = df[cols]
    df = df[[col for col in df.columns if col != 'stock'] + ['stock']]
    
    df.to_csv(output_file, index=False)
    print(f"Archivo procesado exitosamente: {output_file}")
    print(f"Total de filas procesadas: {len(df)}")


if __name__ == "__main__":
    input_file = "../DataBase/products.csv"
    output_file = "../DataBase/inventario_procesado.csv"
    
    process_inventory_csv(input_file, output_file)