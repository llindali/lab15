"""Streamlit controls and presentation; all portfolio math lives in portfolio.py."""
from io import BytesIO
import hashlib
import streamlit as st
import portfolio as engine

st.set_page_config(page_title='Portfolio Stability', layout='wide')
st.title('Portfolio Stability Decision')
st.caption('Built with AI help, a learning demonstration, not investment advice.')
objective = st.sidebar.number_input('Return objective (%)', value=6.5, step=0.1) / 100
minimum = st.sidebar.number_input('Reserve minimum (%)', min_value=0.0, max_value=100.0, value=3.0, step=1.0) / 100
upload = st.sidebar.file_uploader('Monthly adjusted prices (CSV)', type='csv')
last36 = st.sidebar.checkbox('Use last 36 months', value=False)
try:
    if upload:
        raw = upload.getvalue()
        source = hashlib.sha256(raw).hexdigest()[:16]
        loaded, loaded_corr = engine.estimate_prices(BytesIO(raw))
        current, corr = engine.estimate_prices(BytesIO(raw), last36)
        st.caption('Historical annual return estimates; not forecasts. Gross of fees unless adjusted in the return boxes.')
    else:
        source = 'Meridian'
        loaded, loaded_corr = engine.SLEEVES, engine.CORRELATION
        current, corr = loaded, loaded_corr
        st.caption('Meridian course training inputs. Upload your CSV to analyze your own universe.')
    st.subheader('Return estimates and reserve eligibility')
    edited, eligible = [], []
    for i, (name, value, vol) in enumerate(current):
        left, right = st.columns([3, 1])
        estimate = left.number_input(name + ' return estimate (%)', value=value * 100,
                                     step=0.1, key=f'{source}-{last36}-{i}-return') / 100
        checked = right.checkbox('Reserve-eligible: ' + name,
                                 value=not upload and i in engine.RESERVE_INDICES,
                                 key=f'{source}-{i}-reserve')
        edited.append((name, estimate, vol))
        if checked:
            eligible.append(i)
    original = engine.search_mix(loaded, loaded_corr, objective, eligible, minimum)
    changed = engine.search_mix(edited, corr, objective, eligible, minimum)

    def display(result, names):
        if result is None:
            st.write('no mix meets the objective')
            return
        st.table([{'Asset': s[0], 'Weight (%)': f'{w * 100:.2f}'}
                  for s, w in zip(names, result['weights'])])
        st.write(f"Return estimate: {result['return_estimate']:.2%}")
        st.write(f"Volatility: {result['volatility']:.2%}")
        st.write(f"Reserve-eligible weight: {result['reserve']:.2%}")

    left, right = st.columns(2)
    with left:
        st.subheader('As loaded — all months')
        display(original, loaded)
    with right:
        st.subheader('Current inputs' + (' — last 36 months' if upload and last36 else ''))
        display(changed, edited)
    if original is not None and changed is not None:
        change = max(abs(a-b) for a, b in zip(original['weights'], changed['weights'])) * 100
        st.metric('Largest weight change (percentage points)', f'{change:.2f}')
    else:
        st.write('Largest weight change: unavailable when either run is infeasible.')
except (ValueError, TypeError, KeyError) as error:
    st.error(str(error))
