"""Kiểm tra diễn giải nhật ký, lọc và tương tác mà không truy cập dữ liệu thật."""
from datetime import date
import unittest

from streamlit.testing.v1 import AppTest
from frontend.nhat_ky import bang_html, dien_giai, loc_nhat_ky, thoi_gian


def entry(action='khoi_tao_admin', **kwargs):
    return dict(nguoi_thuc_hien='thiet_lap_cuc_bo', doi_tuong='baotram', hanh_dong=action,
                chi_tiet=kwargs.get('detail', ''), tao_luc=kwargs.get('time', '2026-10-29T16:23:00'))


def preview():
    from frontend.nhat_ky import hien_nhat_ky
    import streamlit as st
    logs = [dict(nguoi_thuc_hien='baotram', doi_tuong=f'user{i}', hanh_dong='tao_tai_khoan',
                 chi_tiet='user', tao_luc=f'2026-11-{i+1:02d}T09:00:00') for i in range(8)]
    # Mô phỏng dữ liệu mới trên lần tải lại, không ghi database.
    if st.session_state.get('nk_lam_moi'):
        logs.append(dict(nguoi_thuc_hien='baotram', doi_tuong='newuser', hanh_dong='dat_lai_mat_khau',
                         chi_tiet='', tao_luc='2026-11-09T09:00:00'))
    hien_nhat_ky(logs, [dict(ten_dang_nhap='baotram', ten_hien_thi='Bảo Trâm', vai_tro='admin', kich_hoat=1)])


class NhatKyTests(unittest.TestCase):
    def test_bootstrap_describes_existing_account_promotion(self):
        row = dien_giai(entry())
        self.assertEqual(row['user'], 'Hệ thống')
        self.assertEqual(row['action'], 'Cấp quyền quản trị')
        self.assertIn('baotram', row['detail'])
        self.assertEqual(row['time'], '29/10/2026 16:23')

    def test_permission_json_and_unknown_details(self):
        row = dien_giai(entry('cap_nhat_quyen', detail='{"vai_tro":"user","kich_hoat":false}'))
        self.assertIn('quyền người dùng; đã khóa', row['detail'])
        row = dien_giai(entry('cap_nhat_quyen', detail='dữ liệu cũ'))
        self.assertIn('dữ liệu cũ', row['detail'])
        self.assertEqual(dien_giai(entry('muc_moi', detail='nội dung mới'))['detail'], 'nội dung mới')

    def test_search_display_name_and_target_without_accents(self):
        raw = entry('tao_tai_khoan', detail='user')
        raw['nguoi_thuc_hien'] = 'quantri'
        row = dien_giai(raw, {'quantri': 'Bảo Trâm'})
        self.assertEqual(loc_nhat_ky([row], 'bao tram'), [row])
        self.assertEqual(loc_nhat_ky([row], 'baotram'), [row])
        self.assertEqual(loc_nhat_ky([row], action='Xóa tài khoản'), [])

    def test_date_boundaries_and_invalid_time(self):
        row = dien_giai(entry())
        invalid = dien_giai(entry(time='invalid'))
        self.assertEqual(loc_nhat_ky([row, invalid], start=date(2026, 10, 29), end=date(2026, 10, 29)), [row])
        self.assertEqual(loc_nhat_ky([row], start=date(2026, 10, 30)), [])
        self.assertIsNone(thoi_gian(None))
        self.assertEqual(thoi_gian('2026-11-04T20:00:00+00:00').day, 5)

    def test_escaped_html_and_empty_table(self):
        raw = entry('tao_tai_khoan')
        raw['doi_tuong'] = '<script>alert(1)</script>'
        markup = bang_html([dien_giai(raw)])
        self.assertNotIn('<script>', markup)
        self.assertIn('&lt;script&gt;', markup)
        self.assertIn('Người dùng', markup)
        self.assertIn('Chưa có hoạt động', bang_html([]))

    def test_pagination_search_and_refresh(self):
        app = AppTest.from_function(preview).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.button(key='nk_truoc').disabled)
        app.button(key='nk_sau').click().run()
        self.assertEqual(app.session_state.nk_trang, 2)
        self.assertTrue(app.button(key='nk_sau').disabled)
        app.text_input(key='nk_tim').set_value('user0').run()
        self.assertEqual(app.session_state.nk_trang, 1)
        self.assertTrue(app.button(key='nk_sau').disabled)
        app.text_input(key='nk_tim').set_value('').run()
        app.button(key='nk_lam_moi').click().run()
        self.assertIn('Đặt lại mật khẩu', app.selectbox(key='nk_hanh_dong').options)
        app.selectbox(key='nk_hanh_dong').set_value('Đặt lại mật khẩu').run()
        # The selected option disappears in this fixture on the next reload.
        self.assertFalse(app.exception)

    def test_custom_date_filter(self):
        app = AppTest.from_function(preview).run()
        app.selectbox(key='nk_thoi_gian').set_value('Chọn khoảng ngày').run()
        app.date_input(key='nk_khoang_ngay').set_value((date(2026, 11, 2), date(2026, 11, 3))).run()
        self.assertFalse(app.exception)
        markup = '\n'.join(m.value for m in app.markdown)
        self.assertIn('trong 2 hoạt động', markup)
        app.text_input(key='nk_tim').set_value('không tồn tại').run()
        self.assertIn('Không có hoạt động phù hợp', '\n'.join(m.value for m in app.markdown))


if __name__ == '__main__':
    unittest.main()
